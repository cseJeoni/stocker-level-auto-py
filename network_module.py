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
        
        # 1. 블루투스 상시 연결 시작
        if not loop.run_until_complete(self.ble.connect()):
            self.log_signal.emit("❌ 레벨기 연결 실패!")
            return

        # 2. 소켓 서버 생성
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((config.SERVER_HOST, config.SERVER_PORT))
        server.listen(1)
        server.settimeout(1.0)
        self.log_signal.emit(f"🚀 서버 대기 중 (Port: {config.SERVER_PORT})")

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

                        # 측정 및 기록
                        x, y = loop.run_until_complete(self.ble.read_level_data())
                        if x is not None:
                            if self.excel.write_to_active_sheet(loc, x, y):
                                self.log_signal.emit(f"✅ 완료: {loc} ({x}, {y})")
                                client.sendall(f"DONE|{loc}\n".encode('utf-8'))
                            else:
                                self.log_signal.emit(f"⚠️ 위치 없음: {loc}")
                                client.sendall(f"ERROR|NOT_FOUND|{loc}\n".encode('utf-8'))
                        else:
                            self.log_signal.emit(f"⚠️ {loc} 측정 실패")
                            client.sendall(f"ERROR|BLE_FAIL|{loc}\n".encode('utf-8'))
                client.close()
            except socket.timeout: continue
        
        loop.run_until_complete(self.ble.disconnect())
        server.close()
        loop.close()