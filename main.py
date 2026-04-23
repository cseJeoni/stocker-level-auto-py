import sys
import threading
import asyncio
import traceback
import datetime
import multiprocessing
from PyQt5.QtWidgets import QApplication, QTableWidgetItem
from PyQt5.QtCore import pyqtSlot, QTime, pyqtSignal, Qt
from ui_main import MainUI
from ble_module import scan_devices
from network_module import AutomationServer


# In --noconsole EXE builds, stderr is suppressed and unhandled exceptions cause a
# silent crash. This hook redirects them to a log file for post-mortem diagnosis.
def _handle_exception(exc_type, exc_value, exc_tb):
    try:
        with open("crash_log.txt", "a", encoding="utf-8") as f:
            f.write(f"\n=== UNHANDLED EXCEPTION {datetime.datetime.now()} ===\n")
            traceback.print_exception(exc_type, exc_value, exc_tb, file=f)
    except Exception:
        pass

sys.excepthook = _handle_exception


class MainController(MainUI):
    # Signals used to receive data from background threads into the UI thread safely.
    device_found_signal = pyqtSignal(str)
    log_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.btn_scan.clicked.connect(self.start_scan)
        self.btn_ready.clicked.connect(self.start_automation)
        self.btn_manual_measure.clicked.connect(self.do_manual_measure)
        self.device_found_signal.connect(lambda info: self.cb_ble.addItem(info))
        self.log_signal.connect(self.add_log)

    def start_scan(self):
        # BLE discovery is offloaded to a daemon thread to keep the UI responsive.
        self.cb_ble.clear()
        self.add_log("[INFO] Scanning for devices...")
        threading.Thread(target=self.run_scan, daemon=True).start()

    def run_scan(self):
        # Runs async BLE discovery in a dedicated event loop, then forwards each
        # discovered device to the UI via signal.
        loop = asyncio.new_event_loop()
        try:
            devices = loop.run_until_complete(scan_devices())
        finally:
            loop.close()
        for d in devices:
            self.device_found_signal.emit(d)
        self.log_signal.emit("[INFO] Scan complete.")

    def start_automation(self):
        # Parses the MAC address from the combo box display string, wires up the
        # server's signals to the UI slots, then starts the background worker thread.
        if self.cb_ble.currentIndex() == -1:
            return
        addr = self.cb_ble.currentText().split("(")[-1].replace(")", "")
        self.server = AutomationServer(addr, self.cb_stocker.currentText())
        self.server.log_signal.connect(self.add_log)
        self.server.table_signal.connect(self.update_table)
        self.server.ready_signal.connect(self._on_server_ready)
        self.server.manual_result_signal.connect(self._on_measure_result)
        self.server.start()
        self.btn_ready.setEnabled(False)
        self.btn_ready.setText("RUNNING...")

    @pyqtSlot()
    def _on_server_ready(self):
        # Enables the MEASURE button once the server confirms BLE is connected
        # and the TCP server is actively listening.
        self.btn_manual_measure.setEnabled(True)

    def do_manual_measure(self):
        # Delegates the read request to the server thread via an Event flag.
        # The server processes it on its own asyncio loop, avoiding any
        # cross-thread BLE access.
        self.btn_manual_measure.setEnabled(False)
        self.lbl_x_val.setText("...")
        self.lbl_y_val.setText("...")
        self.server.request_manual_measure()

    @pyqtSlot(object)
    def _on_measure_result(self, result):
        if result and result[0] is not None:
            x, y = result
            self.lbl_x_val.setText(str(x))
            self.lbl_y_val.setText(str(y))
            self.add_log(f"[INFO] Manual measurement: X={x}, Y={y}")
        else:
            self.lbl_x_val.setText("Error")
            self.lbl_y_val.setText("Error")
            self.add_log("[ERROR] Manual measurement failed. Check BLE connection.")
        self.btn_manual_measure.setEnabled(True)

    @pyqtSlot(list)
    def update_table(self, data):
        # Appends one measurement row to the live data table and scrolls to the bottom.
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
