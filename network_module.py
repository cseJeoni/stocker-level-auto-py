import socket
import asyncio
import threading
import traceback
import datetime
from PyQt5.QtCore import QObject, pyqtSignal
import config
from ble_module import BleHandler 
from csv_module import CSVHandler

class AutomationServer(QObject):
    log_signal = pyqtSignal(str)
    table_signal = pyqtSignal(list)
    ready_signal = pyqtSignal()
    manual_result_signal = pyqtSignal(object)

    def __init__(self, ble_address, stocker_id):
        super().__init__()
        self.ble = BleHandler(ble_address)
        self.csv = CSVHandler(stocker_id)
        self.is_running = True
        self._measure_request = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def request_manual_measure(self):
        self._measure_request.set()

    def _run(self):
        try:
            self._run_internal()
        except Exception:
            _write_crash_log(traceback.format_exc())
            self.log_signal.emit("[ERROR] Fatal error. Check crash_log.txt.")

    def _run_internal(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            loop.run_until_complete(self.ble.connect())
        except Exception as e:
            self.log_signal.emit(f"[ERROR] BLE connection failed: {e}")
            loop.close()
            return

        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server.bind((config.SERVER_HOST, config.SERVER_PORT))
            server.listen(1)
            server.settimeout(1.0)
            self.log_signal.emit("[INFO] Server started.")
            self.ready_signal.emit()

            while self.is_running:
                if self._measure_request.is_set():
                    self._measure_request.clear()
                    self._do_manual_read(loop)
                try:
                    client, _ = server.accept()
                    self._handle_client(client, loop)
                except socket.timeout:
                    continue

        except OSError as e:
            self.log_signal.emit(f"[ERROR] Port binding failed: {e}")
        finally:
            server.close()
            loop.run_until_complete(self.ble.disconnect())
            loop.close()

    def _do_manual_read(self, loop):
        try:
            x, y = loop.run_until_complete(
                asyncio.wait_for(self.ble.read_level_data(), timeout=config.BLE_READ_TIMEOUT)
            )
            self.manual_result_signal.emit((x, y) if x is not None else None)
        except Exception:
            self.manual_result_signal.emit(None)

    def _handle_client(self, client, loop):
        # Set 30-second timeout to detect end of sequence
        client.settimeout(30.0)
        with client:
            while self.is_running:
                try:
                    data = client.recv(1024).decode('utf-8')
                    if not data:
                        break

                    msg = data.strip()
                    self.log_signal.emit(f"[RECV] {msg}")

                    if msg.startswith("MEASURE|"):
                        self._handle_measure(client, loop, msg.split("|")[1])

                    elif msg == "FINISH":
                        # Ignore repeated FINISH signals used for equipment step transition
                        self.log_signal.emit("[INFO] FINISH received (Step transition).")
                        continue

                except socket.timeout:
                    self.log_signal.emit("[INFO] 30s timeout reached. Sequence finished and saved.")
                    break

    def _handle_measure(self, client, loop, loc):
            try:
                # Convert "1-01-01" format to "1-1-1" for Excel macro compatibility
                # Split by '-', convert each part to int (to remove leading zeros), then join back
                parts = loc.split('-')
                loc = "-".join([str(int(p)) for p in parts])
                
                x, y = loop.run_until_complete(
                    asyncio.wait_for(self.ble.read_level_data(), timeout=config.BLE_READ_TIMEOUT)
                )
                if x is None:
                    raise ValueError("READ_ERROR")
                
                # Now 'loc' is in "1-1-1" format when passed to CSV and UI
                res = self.csv.write_row(loc, x, y)
                if res:
                    self.table_signal.emit(res)
                    self.log_signal.emit(f"[INFO] Data saved: {loc} (X: {x}, Y: {y})")
            except Exception:
                self.log_signal.emit(f"[ERROR] BLE read failed at {loc}.")

def _write_crash_log(text):
    try:
        with open("crash_log.txt", "a", encoding="utf-8") as f:
            f.write(f"\n=== CRASH {datetime.datetime.now()} ===\n")
            f.write(text)
    except Exception:
        pass