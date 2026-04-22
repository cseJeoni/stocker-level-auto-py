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
    # 백그라운드 스레드에서 UI 화면(표, 로그)을 직접 건드리면 안 되므로,
    # 데이터를 안전하게 전달하기 위해 Signal (신호) 객체 생성
    log_signal = pyqtSignal(str)    # 로그 텍스트를 UI에 전달
    table_signal = pyqtSignal(list) # CSV에 기록된 데이터 한 줄을 UI 표에 전달

    def __init__(self, ble_address, stocker_id):
        super().__init__()
        self.ble = BleHandler(ble_address)
        self.csv = CSVHandler(stocker_id)
        self.is_running = True
        # daemon=True: 메인 프로그램 창의 X 버튼을 눌러서 끄면, 이 백그라운드 스레드도 즉시 종료됨
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def _run(self):
        # 백그라운드 스레드에서 에러가 나면 콘솔에 안 찍히고 프로그램이 죽어버리는 것을 방지
        try:
            self._run_internal()
        except Exception:
            _write_crash_log(traceback.format_exc())
            self.log_signal.emit("❌ [시스템] 치명적 오류 발생 (crash_log.txt 확인)")

    def _run_internal(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # 1. 블루투스 기기 연결 시도
        try:
            loop.run_until_complete(self.ble.connect())
        except Exception as e:
            self.log_signal.emit(f"❌ [시스템] 레벨기 연결 실패: {e}")
            loop.close()
            return

        # 2. TCP/IP 소켓 서버 설정
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # TIME_WAIT 포트 재사용 허용
        try:
            server.bind((config.SERVER_HOST, config.SERVER_PORT))
            server.listen(1)
            server.settimeout(1.0)  # 1초마다 타임아웃을 발생시켜 while 루프의 is_running 상태를 체크할 수 있게 함
            self.log_signal.emit("🚀 서버 가동 중 (저장경로: 다운로드 폴더)")

            # 3. 클라이언트(설비) 접속 대기 루프
            while self.is_running:
                try:
                    client, _ = server.accept()
                    self._handle_client(client, loop)
                except socket.timeout:
                    continue

        except OSError as e:
            self.log_signal.emit(f"❌ [시스템] 포트 {config.SERVER_PORT} 바인딩 실패: {e}")
        finally:
            # 정상 종료든 오류 종료든 항상 리소스 정리
            server.close()
            loop.run_until_complete(self.ble.disconnect())
            loop.close()

    def _handle_client(self, client, loop):
        # 연결된 설비와의 메시지 수신/처리 루프
        with client:
            while self.is_running:
                data = client.recv(1024).decode('utf-8')
                if not data:
                    break  # 연결이 끊기면 탈출

                msg = data.strip()
                self.log_signal.emit(f"📥 수신 : {msg}")

                if msg.startswith("MEASURE|"):
                    self._handle_measure(client, loop, msg.split("|")[1])

                elif msg.startswith("TIMEOUT|"):
                    loc = msg.split("|")[1]
                    # 실제 원인이 블루투스 끊김인지 파이썬 렉인지 구분하여 로그 출력
                    status = "연결 끊김" if not (self.ble.client and self.ble.client.is_connected) else "응답 지연"
                    self.log_signal.emit(f"⚠️ 타임아웃 : 설비 중단 알림 ({loc}) - 사유: {status}")
                    break

                elif msg == "FINISH":
                    self.log_signal.emit("💾 완료 : CSV 저장 및 세션 종료")
                    break

    def _handle_measure(self, client, loop, loc):
        # 측정 요청 처리: BLE 읽기 → CSV 기록 → 응답 송신
        try:
            # 설정된 시간 (기본 10초) 동안 레벨기에서 값을 읽어옴 (내부적으로 5회 평균 처리)
            x, y = loop.run_until_complete(
                asyncio.wait_for(self.ble.read_level_data(), timeout=config.BLE_READ_TIMEOUT)
            )
            if x is None:
                raise ValueError("READ_ERROR")
            res = self.csv.write_row(loc, x, y)
            if res:
                self.table_signal.emit(res)
                self.log_signal.emit(f"✅ 기록 완료 : {loc} (X:{x}, Y:{y})")
                client.sendall(f"DONE|{loc}\n".encode('utf-8'))
        except Exception:
            # 10초 내에 블루투스에서 값을 못 가져오면 파이썬 측 타임아웃 에러 송신
            self.log_signal.emit(f"❌ 에러 : 블루투스 연결 확인 필요 ({loc})")
            client.sendall(f"ERROR|BLE_DISCONNECT|{loc}\n".encode('utf-8'))


def _write_crash_log(text):
    # EXE 빌드 후 터미널 창이 없을 때 원인 분석에 쓰임
    try:
        with open("crash_log.txt", "a", encoding="utf-8") as f:
            f.write(f"\n=== CRASH {datetime.datetime.now()} ===\n")
            f.write(text)
            f.write("\n")
    except Exception:
        pass
