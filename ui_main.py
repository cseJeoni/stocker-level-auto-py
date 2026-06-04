from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
import config


class MainUI(QMainWindow):
    """
    Defines the main window layout.
    Left panel: stocker selection, BLE device controls, and the system log.
    Right panel: live measurement table populated as data is recorded.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Stocker Level Auto System v3.1 (CSV Mode)")
        self.setGeometry(100, 100, 1000, 700)

        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)

        # --- Left panel: controls and log ---
        left_layout = QVBoxLayout()

        gb_stk = QGroupBox("1. Select Stocker")
        l_stk = QVBoxLayout()
        self.cb_stocker = QComboBox()
        self.cb_stocker.addItems(config.STOCKER_LIST)
        l_stk.addWidget(self.cb_stocker)
        gb_stk.setLayout(l_stk)
        left_layout.addWidget(gb_stk)

        gb_ble = QGroupBox("2. Bluetooth Connection")
        l_ble = QVBoxLayout()
        self.btn_scan = QPushButton("Scan Devices")
        self.cb_ble = QComboBox()
        l_ble.addWidget(self.btn_scan)
        l_ble.addWidget(self.cb_ble)
        gb_ble.setLayout(l_ble)
        left_layout.addWidget(gb_ble)

        self.btn_reset = QPushButton("RESET")
        self.btn_reset.setFixedHeight(40)
        self.btn_reset.setStyleSheet("background-color: #F44336; color: white; font-weight: bold;")
        self.btn_reset.setEnabled(False)
        left_layout.addWidget(self.btn_reset)

        self.btn_ready = QPushButton("READY")
        self.btn_ready.setFixedHeight(65)
        self.btn_ready.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        left_layout.addWidget(self.btn_ready)

        # --- Manual Measurement: pre-flight BLE verification ---
        self.btn_manual_measure = QPushButton("MEASURE")
        self.btn_manual_measure.setFixedHeight(40)
        self.btn_manual_measure.setEnabled(False)
        left_layout.addWidget(self.btn_manual_measure)

        readout_frame = QFrame()
        readout_frame.setFrameShape(QFrame.StyledPanel)
        readout_layout = QHBoxLayout(readout_frame)
        readout_layout.addWidget(QLabel("X:"))
        self.lbl_x_val = QLabel("--")
        self.lbl_x_val.setStyleSheet("font-weight: bold; min-width: 70px;")
        readout_layout.addWidget(self.lbl_x_val)
        readout_layout.addWidget(QLabel("Y:"))
        self.lbl_y_val = QLabel("--")
        self.lbl_y_val.setStyleSheet("font-weight: bold; min-width: 70px;")
        readout_layout.addWidget(self.lbl_y_val)
        readout_layout.addStretch()
        left_layout.addWidget(readout_frame)

        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setStyleSheet("background-color: #1e1e1e; color: #00FF00; font-family: Consolas;")
        left_layout.addWidget(QLabel("System Log:"))
        left_layout.addWidget(self.txt_log)
        main_layout.addLayout(left_layout, 1)

        # --- Right panel: live measurement table ---
        right_layout = QVBoxLayout()
        right_layout.addWidget(QLabel("Live Measurement Data:"))
        self.table_data = QTableWidget()
        self.table_data.setColumnCount(3)
        self.table_data.setHorizontalHeaderLabels(config.CSV_HEADER)
        self.table_data.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        right_layout.addWidget(self.table_data)
        main_layout.addLayout(right_layout, 2)

        self.setCentralWidget(main_widget)
