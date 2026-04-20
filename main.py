import sys
import threading
import asyncio
import traceback
import multiprocessing
from PyQt5.QtWidgets import QApplication, QTableWidgetItem
from PyQt5.QtCore import pyqtSlot, QTime, pyqtSignal, Qt
from ui_main import MainUI
from ble_module import scan_devices
from network_module import AutomationServer

def _handle_exception(exc_type, exc_value, exc_tb):
    import datetime
    try:
        with open("crash_log.txt", "a", encoding="utf-8") as f:
            f.write(f"\n=== UNHANDLED EXCEPTION {datetime.datetime.now()} ===\n")
            traceback.print_exception(exc_type, exc_value, exc_tb, file=f)
    except Exception:
        pass

sys.excepthook = _handle_exception


class MainController(MainUI):
    device_found_signal = pyqtSignal(str)
    log_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.btn_scan.clicked.connect(self.start_scan)
        self.btn_ready.clicked.connect(self.start_automation)
        self.device_found_signal.connect(lambda info: self.cb_ble.addItem(info))
        self.log_signal.connect(self.add_log)

    def start_scan(self):
        self.cb_ble.clear(); self.add_log("📡 스캔 중...")
        threading.Thread(target=self.run_scan, daemon=True).start()

    def run_scan(self):
        loop = asyncio.new_event_loop()
        try:
            devices = loop.run_until_complete(scan_devices())
        finally:
            loop.close()
        for d in devices:
            self.device_found_signal.emit(d)
        self.log_signal.emit("✅ 스캔 완료")

    def start_automation(self):
        if self.cb_ble.currentIndex() == -1:
            return
        addr = self.cb_ble.currentText().split("(")[-1].replace(")", "")
        self.server = AutomationServer(addr, self.cb_stocker.currentText())
        self.server.log_signal.connect(self.add_log)
        self.server.table_signal.connect(self.update_table)
        self.server.start()
        self.btn_ready.setEnabled(False); self.btn_ready.setText("RUNNING...")

    @pyqtSlot(list)
    def update_table(self, data):
        row = self.table_data.rowCount()
        self.table_data.insertRow(row)
        for i, val in enumerate(data):
            item = QTableWidgetItem(str(val))
            item.setTextAlignment(Qt.AlignCenter)
            self.table_data.setItem(row, i, item)
        self.table_data.scrollToBottom()

    @pyqtSlot(str)
    def add_log(self, msg):
        self.txt_log.append(f"[{QTime.currentTime().toString()}] {msg}")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    app = QApplication(sys.argv)
    MainController().show()
    sys.exit(app.exec_())
