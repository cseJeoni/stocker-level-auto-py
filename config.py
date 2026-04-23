# --- BLE Settings ---
BLE_DATA_UUID = "0000EE01-0000-1000-8000-00805F9B34FB" # GATT characteristic UUID for X/Y level data
SCAN_TIMEOUT = 5.0   # Maximum duration (seconds) for BLE device discovery
MIN_NAME_LENGTH = 6  # Minimum device name length for the sensor filter
FILTER_PREFIX = ["3D", "2D"] # Accepted device name prefixes to identify compatible sensors

# --- Averaging Settings ---
AVG_COUNT = 5    # Number of samples collected per measurement
AVG_INTERVAL = 0.1  # Interval (seconds) between samples to reduce vibration noise

# --- CSV and UI Settings ---
STOCKER_LIST = ["5BSTK101", "5BSTK102", "5BSTK103", "5BSTK104", "5BSTK105"]
CSV_HEADER = ["Shelf No", "X-axis", "Y-axis"]

# --- Network Settings ---
SERVER_HOST = '127.0.0.1' # Loopback only — the Python server and equipment controller run on the same PC
SERVER_PORT = 5000
BLE_READ_TIMEOUT = 10.0 # Maximum wait (seconds) for a BLE read before raising an error to the equipment
