import sys
import threading
import asyncio
import traceback
import datetime
import multiprocessing
from PyQt5.QtWidgets import QApplication, QTableWidgetItem
from PyQt5.QtCore import pyqtSlot, QTime, pyqtSignal, Qt, QDateTime
from ui_main import MainUI
from ble_module import scan_devices
from network_module import AutomationServer


def _handle_exception(exc_type, exc_value, exc_tb):
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

        # Server is created once at startup; its TCP socket stays open.
        self.server = AutomationServer()
        self.server.log_signal.connect(self.add_log)
        self.server.table_signal.connect(self.update_table)
        self.server.server_ready_signal.connect(self._on_server_ready)
        self.server.session_ready_signal.connect(self._on_session_ready)
        self.server.manual_result_signal.connect(self._on_measure_result)
        self.server.cycle_done_signal.connect(self._on_cycle_done)
        self.server.start()

        # While a reset is in progress, signals still arriving from the server
        # thread (e.g. an in-flight BLE read) must be ignored so they cannot
        # repopulate the views right after we clear them.
        self._resetting = False

        self.btn_scan.clicked.connect(self.start_scan)
        self.btn_ready.clicked.connect(self.start_session)
        self.btn_reset.clicked.connect(self.reset_session)
        self.btn_manual_measure.clicked.connect(self.do_manual_measure)
        self.device_found_signal.connect(lambda info: self.cb_ble.addItem(info))
        self.log_signal.connect(self.add_log)

    # ── BLE scan ──────────────────────────────────────────────────

    def start_scan(self):
        self.cb_ble.clear()
        self.add_log("[INFO] Scanning for devices...")
        threading.Thread(target=self.run_scan, daemon=True).start()

    def run_scan(self):
        loop = asyncio.new_event_loop()
        try:
            devices = loop.run_until_complete(scan_devices())
        finally:
            loop.close()
        for d in devices:
            self.device_found_signal.emit(d)
        self.log_signal.emit("[INFO] Scan complete.")

    # ── Session start / reset ────────────────────────────────────

    def start_session(self):
        """READY button: connect BLE and start the measurement cycle."""
        if self.cb_ble.currentIndex() == -1:
            return
        addr = self.cb_ble.currentText().split("(")[-1].replace(")", "")
        self.server.start_session(addr, self.cb_stocker.currentText())
        self.btn_ready.setEnabled(False)
        self.btn_ready.setText("RUNNING...")
        self.btn_reset.setEnabled(True)

    def reset_session(self):
        """RESET button: force-close client socket, release BLE, reset UI."""
        # Block any further view updates from the still-running server thread
        # until it confirms the cycle has fully ended (cycle_done_signal).
        self._resetting = True
        self.server.reset_session()
        # Restore button states immediately so the user sees instant feedback,
        # without waiting for the async cycle_done_signal from the server thread.
        self.btn_ready.setText("READY")
        self.btn_ready.setEnabled(True)
        self.btn_reset.setEnabled(False)
        self.btn_manual_measure.setEnabled(False)
        self.lbl_x_val.setText("--")
        self.lbl_y_val.setText("--")
        self._clear_views()

    def _clear_views(self):
        """Empty the table, BLE device list and system log."""
        self.table_data.setRowCount(0)
        self.cb_ble.clear()
        self.txt_log.clear()

    # ── Server signal slots ──────────────────────────────────────

    @pyqtSlot()
    def _on_server_ready(self):
        """TCP server bound — called once right after startup."""
        pass  # Logging is emitted directly from the server thread.

    @pyqtSlot()
    def _on_session_ready(self):
        """BLE connected — enable the MEASURE button."""
        self.btn_manual_measure.setEnabled(True)

    @pyqtSlot()
    def _on_cycle_done(self):
        """Cycle ended (normal / timeout / reset) — restore buttons."""
        self.btn_ready.setText("READY")
        self.btn_ready.setEnabled(True)
        self.btn_reset.setEnabled(False)
        self.btn_manual_measure.setEnabled(False)
        if self._resetting:
            # Server thread has fully stopped: wipe any late updates that
            # slipped in before it halted, then resume normal UI updates.
            self._clear_views()
            self._resetting = False
            self.add_log("[INFO] Reset complete.")

    # ── Manual measurement ───────────────────────────────────────

    def do_manual_measure(self):
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

    # ── Table / log ──────────────────────────────────────────────

    @pyqtSlot(list)
    def update_table(self, data):
        # Drop late rows from an in-flight measurement while resetting.
        if self._resetting:
            return
        row = self.table_data.rowCount()
        self.table_data.insertRow(row)
        for i, val in enumerate(data):
            item = QTableWidgetItem(str(val))
            item.setTextAlignment(Qt.AlignCenter)
            self.table_data.setItem(row, i, item)
        self.table_data.scrollToBottom()

    @pyqtSlot(str)
    def add_log(self, msg):
        # Suppress server-thread log noise while resetting; the log is wiped
        # and a single "Reset complete" line is shown once the cycle ends.
        if self._resetting:
            return
        timestamp = QDateTime.currentDateTime().toString("HH:mm:ss.zzz")
        self.txt_log.append(f"[{timestamp}] {msg}")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    app = QApplication(sys.argv)
    MainController().show()
    sys.exit(app.exec_())
