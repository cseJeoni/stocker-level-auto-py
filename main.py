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


# 글로벌 에러 캐쳐: UI 스레드에서 발생하는 런타임 에러가 발생했을 때 프로그램이 튕기지 않고
# crash_log.txt에 기록
def _handle_exception(exc_type, exc_value, exc_tb):
    try:
        with open("crash_log.txt", "a", encoding="utf-8") as f:
            f.write(f"\n=== UNHANDLED EXCEPTION {datetime.datetime.now()} ===\n")
            traceback.print_exception(exc_type, exc_value, exc_tb, file=f)
    except Exception:
        pass

sys.excepthook = _handle_exception


class MainController(MainUI):
    # 스캔 결과와 로그를 UI로 받아오기 위한 Signal 설정
    device_found_signal = pyqtSignal(str)
    log_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.btn_scan.clicked.connect(self.start_scan)
        self.btn_ready.clicked.connect(self.start_automation)
        # 기기를 찾으면 콤보박스에 추가하도록 연결
        self.device_found_signal.connect(lambda info: self.cb_ble.addItem(info))
        self.log_signal.connect(self.add_log)

    def start_scan(self):
        # 스캔 버튼을 눌렀을 때 UI가 멈추지 않도록 백그라운드 스레드에서 스캔 진행
        self.cb_ble.clear()
        self.add_log("📡 스캔 중...")
        threading.Thread(target=self.run_scan, daemon=True).start()

    def run_scan(self):
        loop = asyncio.new_event_loop()
        try:
            devices = loop.run_until_complete(scan_devices())
        finally:
            loop.close()
        for d in devices:
            self.device_found_signal.emit(d)  # 찾은 기기를 UI에 전달
        self.log_signal.emit("✅ 스캔 완료")

    def start_automation(self):
        # READY 버튼 클릭 시 서버와 통신을 시작
        if self.cb_ble.currentIndex() == -1:  # 선택된 기기가 없으면 무시
            return
        addr = self.cb_ble.currentText().split("(")[-1].replace(")", "")
        self.server = AutomationServer(addr, self.cb_stocker.currentText())
        self.server.log_signal.connect(self.add_log)
        self.server.table_signal.connect(self.update_table)
        self.server.start()
        self.btn_ready.setEnabled(False)
        self.btn_ready.setText("RUNNING...")

    @pyqtSlot(list)
    def update_table(self, data):
        # 백그라운드에서 받은 CSV 한 줄 데이터를 오른쪽 표에 그려줌
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
