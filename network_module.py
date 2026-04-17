import socket
import asyncio
from PyQt5.QtCore import QThread, pyqtSignal
import config
from ble_module import BleHandler
from csv_module import CSVHandler

class AutomationServer(QThread):
    log_signal = pyqtSignal(str)
    table_signal = pyqtSignal(list)
    
    def __init__(self, ble_address, stocker_id):
        super().__init__()
        self.ble = BleHandler(ble_address)
        self.csv = CSVHandler(stocker_id)
        self.is_running = True

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(self.ble.connect())
        except Exception:
            self.log_signal.emit("❌ [시스템] 레벨기 연결 실패")
            return

        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((config.SERVER_HOST, config.SERVER_PORT))
        server.listen(1)
        server.settimeout(1.0)
        
        self.log_signal.emit(f"🚀 서버 가동 중 (저장경로: 다운로드 폴더)")

        while self.is_running:
            try:
                client, addr = server.accept()
                while self.is_running:
                    data = client.recv(1024).decode('utf-8')
                    if not data: break
                    msg = data.strip()
                    
                    # 1. 수신 로그 간결화
                    self.log_signal.emit(f"📥 수신 : {msg}")
                    
                    # 2. 측정 명령 처리
                    if msg.startswith("MEASURE|"):
                        loc = msg.split("|")[1]
                        try:
                            # 블루투스 데이터 읽기 (10초 타임아웃)
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
                            # 파이썬이 먼저 감지한 에러
                            self.log_signal.emit(f"❌ 에러 : 블루투스 연결 확인 필요 ({loc})")
                            client.sendall(f"ERROR|BLE_DISCONNECT|{loc}\n".encode('utf-8'))
                            
                    # 3. 설비 측 타임아웃 통보 처리 (2중 안전장치)
                    elif msg.startswith("TIMEOUT|"):
                        loc = msg.split("|")[1]
                        status = "연결 끊김" if not (self.ble.client and self.ble.client.is_connected) else "응답 지연"
                        self.log_signal.emit(f"⚠️ 타임아웃 : 설비 중단 알림 ({loc}) - 사유: {status}")
                        break
                            
                    # 4. 종료 처리
                    elif msg == "FINISH":
                        self.log_signal.emit(f"💾 완료 : CSV 저장 및 세션 종료")
                        break 
                        
                client.close()
            except socket.timeout:
                continue
            
        loop.run_until_complete(self.ble.disconnect())
        server.close()
        loop.close()