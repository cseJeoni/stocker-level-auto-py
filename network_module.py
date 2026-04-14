import socket
import asyncio
from PyQt5.QtCore import QThread, pyqtSignal
import config
from ble_module import BleHandler
from excel_module import ExcelHandler

class AutomationServer(QThread):
    log_signal = pyqtSignal(str)
    
    def __init__(self, ble_address, excel_path):
        super().__init__()
        self.ble = BleHandler(ble_address)
        self.excel = ExcelHandler(excel_path)
        self.is_running = True

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(self.ble.connect())
        except Exception as e:
            self.log_signal.emit(f"❌ 초기 연결 실패: {str(e)}")
            return

        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((config.SERVER_HOST, config.SERVER_PORT))
        server.listen(1)
        server.settimeout(1.0)
        self.log_signal.emit(f"🚀 서버 READY (Port: {config.SERVER_PORT})")

        while self.is_running:
            try:
                client, addr = server.accept()
                self.log_signal.emit(f"🔗 설비 연결됨: {addr}")
                while self.is_running:
                    data = client.recv(1024).decode('utf-8')
                    if not data: break
                    msg = data.strip()
                    if msg.startswith("MEASURE|"):
                        loc = msg.split("|")[1]
                        self.log_signal.emit(f"📥 명령 수신: [{loc}]")
                        
                        try:
                            # 1. 평균값 측정 (타임아웃 적용)
                            x, y = loop.run_until_complete(
                                asyncio.wait_for(self.ble.read_level_data(), timeout=config.BLE_READ_TIMEOUT)
                            )
                            
                            if x is not None:
                                # 2. 엑셀 기록
                                if self.excel.write_to_active_sheet(loc, x, y):
                                    self.log_signal.emit(f"✅ 완료: {loc} ({x}, {y})")
                                    client.sendall(f"DONE|{loc}\n".encode('utf-8'))
                                else:
                                    # [에러 처리] 쉘프 번호 없음
                                    self.log_signal.emit(f"⚠️ NO_SHELF 에러: {loc}")
                                    client.sendall(f"ERROR|NO_SHELF|{loc}\n".encode('utf-8'))
                            else:
                                raise Exception("BLE_FAIL")
                                
                        except Exception:
                            # [에러 처리] 블루투스 끊김 등
                            self.log_signal.emit(f"❌ BLE_DISCONNECT 에러: {loc}")
                            client.sendall(f"ERROR|BLE_DISCONNECT|{loc}\n".encode('utf-8'))
                client.close()
            except socket.timeout: continue
        
        loop.run_until_complete(self.ble.disconnect())
        server.close()
        loop.close()