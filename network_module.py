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
    # Qt signals are used for all cross-thread UI updates. The background thread
    # emits these instead of touching UI widgets directly, which is not thread-safe.
    log_signal = pyqtSignal(str)    # Delivers status messages to the log panel.
    table_signal = pyqtSignal(list) # Delivers a recorded row to the live data table.
    ready_signal = pyqtSignal()     # Fired once BLE is connected and the TCP server is listening.
    manual_result_signal = pyqtSignal(object)  # Fired with (x, y) or None after a manual read.

    def __init__(self, ble_address, stocker_id):
        super().__init__()
        self.ble = BleHandler(ble_address)
        self.csv = CSVHandler(stocker_id)
        self.is_running = True
        self._measure_request = threading.Event()
        # daemon=True ensures the thread is terminated automatically when the main window closes.
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def request_manual_measure(self):
        # Called from the UI thread. Sets an event that the server thread checks
        # between client connections, so the BLE read runs on the server's own
        # event loop with no cross-thread asyncio access.
        self._measure_request.set()

    def _run(self):
        # Top-level thread entry point. Any exception that escapes _run_internal
        # is written to the crash log and surfaced to the UI before the thread exits.
        try:
            self._run_internal()
        except Exception:
            _write_crash_log(traceback.format_exc())
            self.log_signal.emit("[ERROR] Fatal error. See crash_log.txt for details.")

    def _run_internal(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Establish BLE connection first. If this fails, there is nothing to measure,
        # so the thread exits immediately after releasing the event loop.
        try:
            loop.run_until_complete(self.ble.connect())
        except Exception as e:
            self.log_signal.emit(f"[ERROR] Failed to connect to level sensor: {e}")
            loop.close()
            return

        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Allows immediate rebind after restart.
        try:
            server.bind((config.SERVER_HOST, config.SERVER_PORT))
            server.listen(1)
            # A 1-second accept timeout allows the loop to check is_running periodically
            # without blocking indefinitely on accept().
            server.settimeout(1.0)
            self.log_signal.emit("[INFO] Server started. Output path: Downloads folder")
            self.ready_signal.emit()

            while self.is_running:
                # Process a pending manual read before blocking on accept().
                # This keeps the BLE read on the server thread's own event loop.
                if self._measure_request.is_set():
                    self._measure_request.clear()
                    self._do_manual_read(loop)
                try:
                    client, _ = server.accept()
                    self._handle_client(client, loop)
                except socket.timeout:
                    continue

        except OSError as e:
            self.log_signal.emit(f"[ERROR] Port {config.SERVER_PORT} binding failed: {e}")
        finally:
            # Guaranteed cleanup on both normal exit and error exit.
            server.close()
            loop.run_until_complete(self.ble.disconnect())
            loop.close()

    def _do_manual_read(self, loop):
        # Performs a single averaged BLE read and emits the result.
        # Runs entirely on the server thread to avoid cross-thread asyncio access.
        try:
            x, y = loop.run_until_complete(
                asyncio.wait_for(self.ble.read_level_data(), timeout=config.BLE_READ_TIMEOUT)
            )
            self.manual_result_signal.emit((x, y) if x is not None else None)
        except Exception:
            self.manual_result_signal.emit(None)

    def _handle_client(self, client, loop):
        # Drives the message exchange with a connected equipment client.
        # Three command types are handled: measurement requests, equipment-side
        # timeout notifications, and session completion signals.
        with client:
            while self.is_running:
                data = client.recv(1024).decode('utf-8')
                if not data:
                    break

                msg = data.strip()
                self.log_signal.emit(f"[RECV] {msg}")

                if msg.startswith("MEASURE|"):
                    self._handle_measure(client, loop, msg.split("|")[1])

                elif msg.startswith("TIMEOUT|"):
                    loc = msg.split("|")[1]
                    # Distinguish BLE disconnection from a slow Python response to
                    # provide an actionable diagnosis in the log.
                    status = "BLE disconnected" if not (self.ble.client and self.ble.client.is_connected) else "response delayed"
                    self.log_signal.emit(f"[WARN] Equipment timeout at {loc}. Cause: {status}")
                    break

                elif msg == "FINISH":
                    self.log_signal.emit("[INFO] Session complete. CSV saved.")
                    break

    def _handle_measure(self, client, loop, loc):
        # Full pipeline for a single shelf measurement: read BLE sensor data
        # (averaged over multiple samples), write to CSV, update the UI table,
        # then send DONE to release the equipment interlock.
        # Any failure at any stage sends ERROR so the equipment does not wait indefinitely.
        try:
            x, y = loop.run_until_complete(
                asyncio.wait_for(self.ble.read_level_data(), timeout=config.BLE_READ_TIMEOUT)
            )
            if x is None:
                raise ValueError("READ_ERROR")
            res = self.csv.write_row(loc, x, y)
            if res:
                self.table_signal.emit(res)
                self.log_signal.emit(f"[INFO] Data saved: {loc} (X: {x}, Y: {y})")
                client.sendall(f"DONE|{loc}\n".encode('utf-8'))
        except Exception:
            self.log_signal.emit(f"[ERROR] BLE read failed at {loc}. Check sensor connection.")
            client.sendall(f"ERROR|BLE_DISCONNECT|{loc}\n".encode('utf-8'))


def _write_crash_log(text):
    # In --noconsole EXE builds, stderr output is suppressed. This function
    # persists the full traceback to a file for post-mortem diagnosis.
    try:
        with open("crash_log.txt", "a", encoding="utf-8") as f:
            f.write(f"\n=== CRASH {datetime.datetime.now()} ===\n")
            f.write(text)
            f.write("\n")
    except Exception:
        pass
