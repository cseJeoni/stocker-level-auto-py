# [블루투스 설정]
BLE_DATA_UUID = "0000EE01-0000-1000-8000-00805F9B34FB" #
SCAN_TIMEOUT = 5.0
MIN_NAME_LENGTH = 6 #
FILTER_PREFIX = ["3D", "2D"] #

# [평균 측정 설정] - 신규 반영
AVG_COUNT = 5        # 0.5초 동안 5번 측정
AVG_INTERVAL = 0.1   # 측정 간격 (0.1초)

# [엑셀 매핑 설정] - VBA 분석 결과
XL_START_ROW = 9
XL_B1_SHELF = 3; XL_B1_X = 7; XL_B1_Y = 14
XL_B2_SHELF = 36; XL_B2_X = 40; XL_B2_Y = 47

# [네트워크 및 타임아웃 설정] -
SERVER_HOST = '0.0.0.0'
SERVER_PORT = 5000
BLE_READ_TIMEOUT = 10.0  # 전체 측정 프로세스 타임아웃