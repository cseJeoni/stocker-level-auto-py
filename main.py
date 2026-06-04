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

        # 서버는 앱 시작 시 1회 생성 — TCP 소켓은 계속 유지된다
        self.server = AutomationServer()
        self.server.log_signal.connect(self.add_log)
        self.server.table_signal.connect(self.update_table)
        self.server.server_ready_signal.connect(self._on_server_ready)
        self.server.session_ready_signal.connect(self._on_session_ready)
        self.server.manual_result_signal.connect(self._on_measure_result)
        self.server.cycle_done_signal.connect(self._on_cycle_done)
        self.server.start()

        self.btn_scan.clicked.connect(self.start_scan)
        self.btn_ready.clicked.connect(self.start_session)
        self.btn_reset.clicked.connect(self.reset_session)
        self.btn_manual_measure.clicked.connect(self.do_manual_measure)
        self.device_found_signal.connect(lambda info: self.cb_ble.addItem(info))
        self.log_signal.connect(self.add_log)

    # ── BLE 스캔 ──────────────────────────────────────────────────

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

    # ── 세션 시작 / 리셋 ─────────────────────────────────────────

    def start_session(self):
        """READY 버튼: BLE 연결 + 측정 사이클 시작"""
        if self.cb_ble.currentIndex() == -1:
            return
        addr = self.cb_ble.currentText().split("(")[-1].replace(")", "")
        self.server.start_session(addr, self.cb_stocker.currentText())
        self.btn_ready.setEnabled(False)
        self.btn_ready.setText("RUNNING...")
        self.btn_reset.setEnabled(True)

    def reset_session(self):
        """RESET 버튼: 클라이언트 소켓 강제 종료 + BLE 해제 + UI 초기화"""
        self.add_log("[INFO] Reset requested by user.")
        self.server.reset_session()
        self.table_data.setRowCount(0)
        self.txt_log.clear()
        self.cb_ble.clear()

    # ── 서버 시그널 슬롯 ─────────────────────────────────────────

    @pyqtSlot()
    def _on_server_ready(self):
        """TCP 서버 바인딩 완료 — 앱 시작 직후 1회만 호출됨"""
        pass  # 로그는 서버 스레드에서 직접 emit

    @pyqtSlot()
    def _on_session_ready(self):
        """BLE 연결 완료 — MEASURE 버튼 활성화"""
        self.btn_manual_measure.setEnabled(True)

    @pyqtSlot()
    def _on_cycle_done(self):
        """사이클 종료(정상/타임아웃/RESET) — 버튼 상태만 복원"""
        self.btn_ready.setText("READY")
        self.btn_ready.setEnabled(True)
        self.btn_reset.setEnabled(False)
        self.btn_manual_measure.setEnabled(False)

    # ── 수동 측정 ────────────────────────────────────────────────

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

    # ── 테이블 / 로그 ────────────────────────────────────────────

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
        timestamp = QDateTime.currentDateTime().toString("HH:mm:ss.zzz")
        self.txt_log.append(f"<[{timestamp}]{msg}")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    app = QApplication(sys.argv)
    MainController().show()
    sys.exit(app.exec_())
