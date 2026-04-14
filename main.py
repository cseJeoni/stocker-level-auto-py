import sys
import threading
import asyncio
from PyQt5.QtWidgets import QApplication, QFileDialog, QMessageBox
from PyQt5.QtCore import pyqtSlot, QTime, pyqtSignal
from PyQt5.QtGui import QTextCursor
from ui_main import MainUI
from ble_module import scan_devices
from network_module import AutomationServer

class MainController(MainUI):
    device_found_signal = pyqtSignal(str)
    log_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.btn_excel.clicked.connect(self.select_excel)
        self.btn_scan.clicked.connect(self.start_scan)
        self.btn_ready.clicked.connect(self.start_automation)
        self.device_found_signal.connect(lambda info: self.cb_ble.addItem(info))
        self.log_signal.connect(self.add_log)

    def select_excel(self):
        path, _ = QFileDialog.getOpenFileName(self, "파일 선택", "", "Excel Files (*.xlsm)")
        if path: self.edit_excel.setText(path)

    def start_scan(self):
        self.cb_ble.clear()
        self.log_signal.emit("📡 장치 스캔 중...")
        threading.Thread(target=self.run_scan, daemon=True).start()

    def run_scan(self):
        loop = asyncio.new_event_loop()
        devices = loop.run_until_complete(scan_devices())
        for d in devices: self.device_found_signal.emit(d)
        self.log_signal.emit("✅ 스캔 완료")

    def start_automation(self):
        if not self.edit_excel.text() or self.cb_ble.currentIndex() == -1:
            QMessageBox.warning(self, "경고", "설정을 완료하세요.")
            return
        addr = self.cb_ble.currentText().split("(")[-1].replace(")", "")
        self.server = AutomationServer(addr, self.edit_excel.text())
        self.server.log_signal.connect(self.add_log)
        self.server.start()
        self.btn_ready.setEnabled(False); self.btn_ready.setText("RUNNING..."); self.btn_ready.setStyleSheet("background-color: #f44336; color: white;")

    @pyqtSlot(str)
    def add_log(self, msg):
        self.txt_log.append(f"[{QTime.currentTime().toString()}] {msg}")
        self.txt_log.moveCursor(QTextCursor.End)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    MainController().show()
    sys.exit(app.exec_())