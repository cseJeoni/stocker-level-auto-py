from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import QTextCursor

class MainUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Stocker Level Auto System v2.0")
        self.setGeometry(100, 100, 520, 680)
        central = QWidget()
        layout = QVBoxLayout(central)

        # 1. 엑셀 설정
        gb_ex = QGroupBox("1. Excel Template Settings")
        l_ex = QHBoxLayout()
        self.edit_excel = QLineEdit(); self.edit_excel.setReadOnly(True)
        self.btn_excel = QPushButton("파일 찾기")
        l_ex.addWidget(self.edit_excel); l_ex.addWidget(self.btn_excel)
        gb_ex.setLayout(l_ex)
        layout.addWidget(gb_ex) # 오타 수정: gb_excel -> gb_ex

        # 2. BLE 설정
        gb_ble = QGroupBox("2. Bluetooth Connection (Level only)")
        l_ble = QVBoxLayout()
        self.cb_ble = QComboBox()
        self.btn_scan = QPushButton("장치 스캔 시작")
        l_ble.addWidget(self.btn_scan); l_ble.addWidget(self.cb_ble)
        gb_ble.setLayout(l_ble)
        layout.addWidget(gb_ble)

        # 3. 제어 버튼
        self.btn_ready = QPushButton("READY (자동화 시작)")
        self.btn_ready.setFixedHeight(65)
        self.btn_ready.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; font-size: 16px;")
        layout.addWidget(self.btn_ready)

        # 로그창
        self.txt_log = QTextEdit(); self.txt_log.setReadOnly(True)
        self.txt_log.setStyleSheet("background-color: #1e1e1e; color: #00FF00; font-family: Consolas;")
        layout.addWidget(QLabel("시스템 로그:"))
        layout.addWidget(self.txt_log)
        self.setCentralWidget(central)