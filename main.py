import sys
import asyncio
import socket
import threading
import os
import xlwings as xw
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import QTextCursor
from bleak import BleakScanner, BleakClient

# [설정 상수]
BLE_DATA_UUID = "0000EE01-0000-1000-8000-00805F9B34FB" #
XL_START_ROW = 9
XL_B1_SHELF = 3; XL_B1_X = 7; XL_B1_Y = 14
XL_B2_SHELF = 36; XL_B2_X = 40; XL_B2_Y = 47

class AutomationServer(QThread):
    log_signal = pyqtSignal(str)
    
    def __init__(self, ble_address, excel_path):
        super().__init__()
        self.ble_address = ble_address
        self.excel_path = excel_path.replace('/', '\\')
        self.is_running = True
        self.ble_client = None  # 블루투스 연결 객체 저장용

    async def maintain_ble_connection(self):
        """블루투스 연결을 시도하고 유지함"""
        try:
            if self.ble_client is None or not self.ble_client.is_connected:
                self.log_signal.emit(f"🔗 레벨기 연결 시도 중: {self.ble_address}")
                self.ble_client = BleakClient(self.ble_address, timeout=10.0)
                await self.ble_client.connect()
                self.log_signal.emit("✅ 레벨기 연결 성공 (연결 유지 모드)")
            return True
        except Exception as e:
            self.log_signal.emit(f"❌ 레벨기 연결 실패: {str(e)}")
            return False

    async def get_measurement(self):
        """연결된 레벨기에서 데이터를 한 번 읽어옴"""
        try:
            if self.ble_client and self.ble_client.is_connected:
                raw_data = await self.ble_client.read_gatt_char(BLE_DATA_UUID)
                decoded = raw_data.decode('ascii')
                parts = decoded.split(':') # 예: "4:0:0.001:0.002"
                if len(parts) >= 4:
                    return float(parts[2]), float(parts[3])
            else:
                self.log_signal.emit("⚠️ 레벨기 연결이 끊겨있습니다. 재연결 시도 중...")
                if await self.maintain_ble_connection():
                    return await self.get_measurement()
        except Exception as e:
            self.log_signal.emit(f"⚠️ 데이터 읽기 실패: {str(e)}")
        return None, None

    def write_to_excel(self, location, x_val, y_val):
        """엑셀 기록 로직 (VBA ActiveSheet 방식 재현)"""
        try:
            app = xw.apps.active if xw.apps.count > 0 else xw.App(visible=True)
            target_name = os.path.basename(self.excel_path)
            target_book = next((b for b in app.books if b.name == target_name), None)
            if not target_book: target_book = app.books.open(self.excel_path)
            
            ws = target_book.sheets.active #
            last_row = ws.range('C' + str(ws.cells.last_cell.row)).end('up').row
            if last_row < XL_START_ROW: last_row = 100
            
            b1_data = ws.range((XL_START_ROW, XL_B1_SHELF), (last_row, XL_B1_SHELF)).value
            b2_data = ws.range((XL_START_ROW, XL_B2_SHELF), (last_row, XL_B2_SHELF)).value

            # 위치 찾기 및 기록
            for data_list, shelf_col, x_col, y_col in [(b1_data, XL_B1_SHELF, XL_B1_X, XL_B1_Y), 
                                                       (b2_data, XL_B2_SHELF, XL_B2_X, XL_B2_Y)]:
                if data_list:
                    for i, val in enumerate(data_list):
                        if val and str(val).strip() == location:
                            row = XL_START_ROW + i
                            ws.cells(row, x_col).value = x_val
                            ws.cells(row, y_col).value = y_val
                            return True
            return False
        except Exception as e:
            self.log_signal.emit(f"⚠️ 엑셀 오류: {str(e)}")
            return False

    def run(self):
        # 1. 전용 이벤트 루프 생성
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # 2. 시작 시 블루투스 먼저 연결
        if not loop.run_until_complete(self.maintain_ble_connection()):
            self.log_signal.emit("🚫 레벨기 연결 실패로 서버를 시작할 수 없습니다.")
            return

        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(('0.0.0.0', 5000))
        server.listen(1)
        server.settimeout(1.0)
        self.log_signal.emit("🚀 서버 READY: 명령 대기 중")

        try:
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

                            # 연결 유지 상태에서 값만 읽어옴 (매우 빠름)
                            x, y = loop.run_until_complete(self.get_measurement())
                            
                            if x is not None:
                                if self.write_to_excel(loc, x, y):
                                    self.log_signal.emit(f"✅ 완료: {loc} (X:{x}, Y:{y})")
                                    client.sendall(f"DONE|{loc}\n".encode('utf-8'))
                                else:
                                    self.log_signal.emit(f"⚠️ {loc} 위치 없음")
                                    client.sendall(f"ERROR|NOT_FOUND|{loc}\n".encode('utf-8'))
                            else:
                                client.sendall(f"ERROR|BLE_FAIL|{loc}\n".encode('utf-8'))
                    client.close()
                except socket.timeout: continue
        finally:
            # 종료 시 블루투스 연결 해제
            if self.ble_client:
                loop.run_until_complete(self.ble_client.disconnect())
            server.close()
            loop.close()

class MainWindow(QMainWindow):
    device_found_signal = pyqtSignal(str)
    scan_finished_signal = pyqtSignal()
    log_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.initUI()
        self.device_found_signal.connect(lambda info: self.cb_ble.addItem(info))
        self.scan_finished_signal.connect(lambda: self.log_signal.emit("✅ 스캔 완료"))
        self.log_signal.connect(self.add_log)

    def initUI(self):
        self.setWindowTitle("Stocker Level Auto System v1.3")
        self.setGeometry(100, 100, 520, 680)
        layout = QVBoxLayout()
        # (생략: 이전과 동일한 UI 코드 - Excel, BLE 콤보박스, READY 버튼, 로그창 포함)
        gb_excel = QGroupBox("1. Excel Template Settings")
        l_excel = QHBoxLayout()
        self.edit_excel = QLineEdit(); self.edit_excel.setReadOnly(True)
        btn_excel = QPushButton("파일 찾기")
        btn_excel.clicked.connect(self.select_excel)
        l_excel.addWidget(self.edit_excel); l_excel.addWidget(btn_excel)
        gb_excel.setLayout(l_excel); layout.addWidget(gb_excel)

        gb_ble = QGroupBox("2. Bluetooth Connection")
        l_ble = QVBoxLayout()
        self.cb_ble = QComboBox()
        btn_scan = QPushButton("장치 스캔")
        btn_scan.clicked.connect(self.start_ble_scan)
        l_ble.addWidget(btn_scan); l_ble.addWidget(self.cb_ble)
        gb_ble.setLayout(l_ble); layout.addWidget(gb_ble)

        self.btn_ready = QPushButton("READY (자동화 시작)")
        self.btn_ready.setFixedHeight(65)
        self.btn_ready.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; font-size: 16px;")
        self.btn_ready.clicked.connect(self.toggle_automation)
        layout.addWidget(self.btn_ready)

        self.txt_log = QTextEdit(); self.txt_log.setReadOnly(True)
        self.txt_log.setStyleSheet("background-color: #1e1e1e; color: #00FF00; font-family: Consolas;")
        layout.addWidget(QLabel("시스템 로그:")); layout.addWidget(self.txt_log)

        container = QWidget(); container.setLayout(layout)
        self.setCentralWidget(container)

    def select_excel(self):
        path, _ = QFileDialog.getOpenFileName(self, "엑셀 선택", "", "Excel Files (*.xlsm)")
        if path: self.edit_excel.setText(path)

    def start_ble_scan(self):
        self.cb_ble.clear()
        self.log_signal.emit("📡 블루투스 기기 검색 중...")
        threading.Thread(target=self.run_async_scan, daemon=True).start()

    def run_async_scan(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            devices = loop.run_until_complete(BleakScanner.discover(timeout=5.0))
            for d in devices:
                if d.name and len(d.name) > 6 and d.name[:2] in ["3D", "2D"]: #
                    self.device_found_signal.emit(f"{d.name} ({d.address})")
            self.scan_finished_signal.emit()
        except Exception as e: self.log_signal.emit(f"⚠️ 스캔 오류: {str(e)}")

    def toggle_automation(self):
        if not self.edit_excel.text() or self.cb_ble.currentIndex() == -1:
            QMessageBox.warning(self, "경고", "파일과 장치를 먼저 선택하세요.")
            return
        addr = self.cb_ble.currentText().split("(")[-1].replace(")", "")
        self.server = AutomationServer(addr, self.edit_excel.text())
        self.server.log_signal.connect(self.add_log)
        self.server.start()
        self.btn_ready.setEnabled(False); self.btn_ready.setText("RUNNING..."); self.btn_ready.setStyleSheet("background-color: #f44336; color: white;")

    @pyqtSlot(str)
    def add_log(self, msg):
        current_time = QTime.currentTime().toString("hh:mm:ss")
        self.txt_log.append(f"[{current_time}] {msg}")
        self.txt_log.moveCursor(QTextCursor.End)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow(); win.show(); sys.exit(app.exec_())