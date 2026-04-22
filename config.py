# [블루투스 및 네트워크 설정]
BLE_DATA_UUID = "0000EE01-0000-1000-8000-00805F9B34FB" # 레벨기에서 X, Y 데이터를 쏴주는 고유 주소 
SCAN_TIMEOUT = 5.0 # 블루투스 스캔 최대 시간 
MIN_NAME_LENGTH = 6 # 기기명 6글자 이상
FILTER_PREFIX = ["3D", "2D"] # 레벨기 이름 시작 

# [평균 측정 설정]
AVG_COUNT = 5 # 총 측정 횟수
AVG_INTERVAL = 0.1 # 측정 간격

# [CSV 및 UI 설정]
STOCKER_LIST = ["5BSTK101", "5BSTK102", "5BSTK103", "5BSTK104", "5BSTK105"] # UI에 표시되는 스토커 이름
CSV_HEADER = ["Shelf No", "X-axis", "Y-axis"] # CSV 파일 헤더 

# [네트워크 설정]
SERVER_HOST = '127.0.0.1' # 단일 PC 내부 통신 IP (자기 자신) 
SERVER_PORT = 5000 # 통신 포트
BLE_READ_TIMEOUT = 10.0 # 블루투스 응답 기다리는 최대 시간 