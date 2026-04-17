from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import QTextCursor
import config

class MainUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Stocker Level Auto System v3.1 (CSV Mode)")
        self.setGeometry(100, 100, 1000, 700)
        
        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)

        # 왼쪽 영역
        left_layout = QVBoxLayout()
        gb_stk = QGroupBox("1. 스토커 선택")
        l_stk = QVBoxLayout()
        self.cb_stocker = QComboBox()
        self.cb_stocker.addItems(config.STOCKER_LIST)
        l_stk.addWidget(self.cb_stocker); gb_stk.setLayout(l_stk); left_layout.addWidget(gb_stk)

        gb_ble = QGroupBox("2. Bluetooth Connection")
        l_ble = QVBoxLayout()
        self.cb_ble = QComboBox(); self.btn_scan = QPushButton("장치 스캔 시작")
        l_ble.addWidget(self.btn_scan); l_ble.addWidget(self.cb_ble)
        gb_ble.setLayout(l_ble); left_layout.addWidget(gb_ble)

        self.btn_ready = QPushButton("READY (자동화 시작)")
        self.btn_ready.setFixedHeight(65)
        self.btn_ready.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        left_layout.addWidget(self.btn_ready)

        self.txt_log = QTextEdit(); self.txt_log.setReadOnly(True)
        self.txt_log.setStyleSheet("background-color: #1e1e1e; color: #00FF00; font-family: Consolas;")
        left_layout.addWidget(QLabel("시스템 로그:")); left_layout.addWidget(self.txt_log)
        main_layout.addLayout(left_layout, 1)

        # 오른쪽 영역 (데이터 테이블)
        right_layout = QVBoxLayout()
        right_layout.addWidget(QLabel("📊 실시간 CSV 기록 데이터:"))
        self.table_data = QTableWidget()
        
        self.table_data.setColumnCount(3)
        self.table_data.setHorizontalHeaderLabels(config.CSV_HEADER)
        self.table_data.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        right_layout.addWidget(self.table_data)
        main_layout.addLayout(right_layout, 2)

        self.setCentralWidget(main_widget)