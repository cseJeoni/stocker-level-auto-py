# [블루투스 설정]
BLE_DATA_UUID = "0000EE01-0000-1000-8000-00805F9B34FB" # [cite: 6]
SCAN_TIMEOUT = 5.0
MIN_NAME_LENGTH = 6 # 이름이 6자 초과인 기기만 스캔 [cite: 4]
FILTER_PREFIX = ["3D", "2D"] # 3D 또는 2D로 시작하는 기기만 [cite: 4]

# [엑셀 매핑 설정] 
XL_START_ROW = 9
XL_B1_SHELF = 3; XL_B1_X = 7; XL_B1_Y = 14
XL_B2_SHELF = 36; XL_B2_X = 40; XL_B2_Y = 47

# [네트워크 설정]
SERVER_HOST = '0.0.0.0'
SERVER_PORT = 5000