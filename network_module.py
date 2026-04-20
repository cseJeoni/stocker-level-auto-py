import sys
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

    def __init__(self, ble_address, stocker_id):
        super().__init__()
        self.ble = BleHandler(ble_address)
        self.csv = CSVHandler(stocker_id)
        self.is_running = True
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def _run(self):
        try:
            self._run_internal()
        except Exception:
            _write_crash_log(traceback.format_exc())
            self.log_signal.emit("❌ [시스템] 치명적 오류 발생 (crash_log.txt 확인)")

    def _run_internal(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            loop.run_until_complete(self.ble.connect())
        except Exception as e:
            self.log_signal.emit(f"❌ [시스템] 레벨기 연결 실패: {e}")
            loop.close()
            return

        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server.bind((config.SERVER_HOST, config.SERVER_PORT))
        except OSError as e:
            self.log_signal.emit(f"❌ [시스템] 포트 {config.SERVER_PORT} 바인딩 실패: {e}")
            loop.run_until_complete(self.ble.disconnect())
            loop.close()
            return

        server.listen(1)
        server.settimeout(1.0)

        self.log_signal.emit(f"🚀 서버 가동 중 (저장경로: 다운로드 폴더)")

        while self.is_running:
            try:
                client, addr = server.accept()
                while self.is_running:
                    data = client.recv(1024).decode('utf-8')
                    if not data:
                        break
                    msg = data.strip()

                    self.log_signal.emit(f"📥 수신 : {msg}")

                    if msg.startswith("MEASURE|"):
                        loc = msg.split("|")[1]
                        try:
                            x, y = loop.run_until_complete(
                                asyncio.wait_for(self.ble.read_level_data(), timeout=config.BLE_READ_TIMEOUT)
                            )
                            if x is not None:
                                res = self.csv.write_row(loc, x, y)
                                if res:
                                    self.table_signal.emit(res)
                                    self.log_signal.emit(f"✅ 기록 완료 : {loc} (X:{x}, Y:{y})")
                                    client.sendall(f"DONE|{loc}\n".encode('utf-8'))
                            else:
                                raise Exception("READ_ERROR")
                        except Exception:
                            self.log_signal.emit(f"❌ 에러 : 블루투스 연결 확인 필요 ({loc})")
                            client.sendall(f"ERROR|BLE_DISCONNECT|{loc}\n".encode('utf-8'))

                    elif msg.startswith("TIMEOUT|"):
                        loc = msg.split("|")[1]
                        status = "연결 끊김" if not (self.ble.client and self.ble.client.is_connected) else "응답 지연"
                        self.log_signal.emit(f"⚠️ 타임아웃 : 설비 중단 알림 ({loc}) - 사유: {status}")
                        break

                    elif msg == "FINISH":
                        self.log_signal.emit(f"💾 완료 : CSV 저장 및 세션 종료")
                        break

                client.close()
            except socket.timeout:
                continue

        loop.run_until_complete(self.ble.disconnect())
        server.close()
        loop.close()


def _write_crash_log(text):
    try:
        log_path = "crash_log.txt"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"\n=== CRASH {datetime.datetime.now()} ===\n")
            f.write(text)
            f.write("\n")
    except Exception:
        pass
