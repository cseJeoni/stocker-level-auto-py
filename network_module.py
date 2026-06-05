import socket
import asyncio
import threading
import traceback
import datetime
from PyQt5.QtCore import QObject, pyqtSignal
import config
from ble_module import BleHandler
from csv_module import CSVHandler


class AutomationServer(QObject):
    log_signal = pyqtSignal(str)
    table_signal = pyqtSignal(list)
    server_ready_signal = pyqtSignal()   # TCP 소켓 바인딩 완료
    session_ready_signal = pyqtSignal()  # BLE 연결 완료, 클라이언트 대기 중
    manual_result_signal = pyqtSignal(object)
    cycle_done_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._loop = None
        self._ble = None
        self._csv = None
        self._ble_address = None
        self._stocker_id = None

        self._current_client = None          # 현재 활성 클라이언트 소켓
        self._session_event = threading.Event()  # start_session() 호출 시 set
        self._reset_requested = False
        self._measure_request = threading.Event()
        self._server_running = True          # 서버 스레드 전체 생애주기

    # ── 외부 호출 API ─────────────────────────────────────────────

    def start(self):
        """앱 시작 시 1회 호출. TCP 서버 스레드를 시작한다."""
        threading.Thread(target=self._run, daemon=True).start()

    def start_session(self, ble_address, stocker_id):
        """READY 버튼 클릭 시 호출. BLE 연결 + 클라이언트 수락 사이클을 시작한다."""
        self._ble_address = ble_address
        self._stocker_id = stocker_id
        self._csv = CSVHandler(stocker_id)
        self._reset_requested = False
        self._session_event.set()

    def reset_session(self):
        """RESET 버튼 클릭 시 호출. 활성 클라이언트 소켓을 즉시 닫고 BLE 해제를 요청한다."""
        self._reset_requested = True
        # 연결 중인 클라이언트 소켓 강제 클로즈 → _handle_client recv()가 즉시 깨어남
        if self._current_client is not None:
            try:
                self._current_client.close()
            except Exception:
                pass

    def request_manual_measure(self):
        self._measure_request.set()

    # ── 서버 스레드 ───────────────────────────────────────────────

    def _run(self):
        try:
            self._run_internal()
        except Exception:
            _write_crash_log(traceback.format_exc())
            self.log_signal.emit("[ERROR] Fatal error. Check crash_log.txt.")

    def _run_internal(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server_sock.bind((config.SERVER_HOST, config.SERVER_PORT))
            server_sock.listen(1)
            server_sock.settimeout(1.0)
            self.log_signal.emit("[INFO] Server started. Waiting for session...")
            self.server_ready_signal.emit()

            # 서버 소켓은 앱 종료 전까지 유지 — 포트 충돌 없음
            while self._server_running:
                # READY 버튼이 눌릴 때까지 대기
                if not self._session_event.wait(timeout=0.5):
                    continue
                self._session_event.clear()
                self._reset_requested = False

                # ── BLE 연결 ──
                self._ble = BleHandler(self._ble_address)
                try:
                    self._loop.run_until_complete(self._ble.connect())
                except Exception as e:
                    self.log_signal.emit(f"[ERROR] BLE connection failed: {e}")
                    self._end_cycle()
                    continue

                self.log_signal.emit("[INFO] BLE connected. Waiting for equipment...")
                self.session_ready_signal.emit()

                # ── 클라이언트 연결 수락 ──
                client_sock = None
                while self._server_running and not self._reset_requested:
                    try:
                        client_sock, addr = server_sock.accept()
                        self._current_client = client_sock
                        self.log_signal.emit(f"[INFO] Client connected: {addr}")
                        break
                    except socket.timeout:
                        continue

                # RESET이 accept 대기 중 발생한 경우
                if self._reset_requested or client_sock is None:
                    self._end_cycle()
                    continue

                # ── 클라이언트 세션 처리 ──
                self._handle_client(client_sock, self._loop)
                self._end_cycle()

        except OSError as e:
            self.log_signal.emit(f"[ERROR] Port binding failed: {e}")
        finally:
            server_sock.close()
            self._loop.close()

    def _end_cycle(self):
        """BLE 해제 + 로그 + UI 복원 시그널 발행"""
        if self._ble is not None:
            try:
                self._loop.run_until_complete(self._ble.disconnect())
            except Exception:
                pass
            self._ble = None
        self._current_client = None
        self.log_signal.emit("Cycle terminated. BLE disconnected.")
        self.cycle_done_signal.emit()

    # ── 클라이언트 메시지 처리 ───────────────────────────────────

    def _handle_client(self, client, loop):
        client.settimeout(30.0)
        with client:
            while True:
                try:
                    data = client.recv(1024).decode('utf-8')
                    if not data:
                        break
                    msg = data.strip()
                    self.log_signal.emit(msg)
                    if msg.startswith("MEASURE|"):
                        self._handle_measure(client, loop, msg.split("|")[1])
                except socket.timeout:
                    self.log_signal.emit("30s timeout reached. Sequence finished.")
                    break
                except OSError:
                    # reset_session()의 강제 close()로 인한 소켓 에러 — 정상 종료
                    break

    def _handle_measure(self, client, loop, loc):
        try:
            parts = loc.split('-')
            loc_converted = "-".join([str(int(p)) for p in parts])
            x, y = loop.run_until_complete(
                asyncio.wait_for(self._ble.read_level_data(), timeout=config.BLE_READ_TIMEOUT)
            )
            if x is None:
                raise ValueError("READ_ERROR")
            res = self._csv.write_row(loc_converted, x, y)
            if res:
                self.table_signal.emit(res)
        except Exception:
            self.log_signal.emit(f"BLE read failed at {loc}.")

    # ── 수동 측정 ────────────────────────────────────────────────

    def _do_manual_read(self, loop):
        try:
            x, y = loop.run_until_complete(
                asyncio.wait_for(self._ble.read_level_data(), timeout=config.BLE_READ_TIMEOUT)
            )
            self.manual_result_signal.emit((x, y) if x is not None else None)
        except Exception:
            self.manual_result_signal.emit(None)


def _write_crash_log(text):
    try:
        with open("crash_log.txt", "a", encoding="utf-8") as f:
            f.write(f"\n=== CRASH {datetime.datetime.now()} ===\n")
            f.write(text)
    except Exception:
        pass
