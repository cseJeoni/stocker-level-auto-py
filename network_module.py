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
    server_ready_signal = pyqtSignal()   # TCP socket bound
    session_ready_signal = pyqtSignal()  # BLE connected, awaiting client
    manual_result_signal = pyqtSignal(object)
    cycle_done_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._loop = None
        self._ble = None
        self._csv = None
        self._ble_address = None
        self._stocker_id = None

        self._current_client = None          # currently active client socket
        self._session_event = threading.Event()  # set when start_session() is called
        self._reset_requested = False
        self._measure_request = threading.Event()
        self._server_running = True          # whole server-thread lifetime

    # ── External API ──────────────────────────────────────────────

    def start(self):
        """Called once at startup. Starts the TCP server thread."""
        threading.Thread(target=self._run, daemon=True).start()

    def start_session(self, ble_address, stocker_id):
        """Called on READY click. Starts the BLE-connect + client-accept cycle."""
        self._ble_address = ble_address
        self._stocker_id = stocker_id
        self._csv = CSVHandler(stocker_id)
        self._reset_requested = False
        self._session_event.set()

    def reset_session(self):
        """Called on RESET click. Immediately closes the active client socket and requests BLE release."""
        self._reset_requested = True
        # Force-close the connected client socket so _handle_client recv() wakes up immediately.
        if self._current_client is not None:
            try:
                self._current_client.close()
            except Exception:
                pass

    def request_manual_measure(self):
        self._measure_request.set()

    # ── Server thread ─────────────────────────────────────────────

    def _run(self):
        try:
            self._run_internal()
        except Exception:
            _write_crash_log(traceback.format_exc())
            self.log_signal.emit("[ERROR] Fatal error. Check crash_log.txt.")

    def _run_internal(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server_sock.bind((config.SERVER_HOST, config.SERVER_PORT))
            server_sock.listen(1)
            server_sock.settimeout(1.0)
            self.log_signal.emit("[INFO] Server started. Waiting for session...")
            self.server_ready_signal.emit()

            # Server socket stays open until app exit — no port conflicts.
            while self._server_running:
                # Wait until the READY button is pressed.
                if not self._session_event.wait(timeout=0.5):
                    continue
                self._session_event.clear()
                self._reset_requested = False

                # ── BLE connect ──
                self._ble = BleHandler(self._ble_address)
                try:
                    self._loop.run_until_complete(self._ble.connect())
                except Exception as e:
                    self.log_signal.emit(f"[ERROR] BLE connection failed: {e}")
                    self._end_cycle()
                    continue

                self.log_signal.emit("[INFO] BLE connected. Waiting for equipment...")
                self.session_ready_signal.emit()

                # ── Accept client connection ──
                client_sock = None
                while self._server_running and not self._reset_requested:
                    try:
                        client_sock, addr = server_sock.accept()
                        self._current_client = client_sock
                        self.log_signal.emit(f"[INFO] Client connected: {addr}")
                        break
                    except socket.timeout:
                        continue

                # RESET happened while waiting in accept().
                if self._reset_requested or client_sock is None:
                    self._end_cycle()
                    continue

                # ── Handle client session ──
                self._handle_client(client_sock, self._loop)
                self._end_cycle()

        except OSError as e:
            self.log_signal.emit(f"[ERROR] Port binding failed: {e}")
        finally:
            server_sock.close()
            self._loop.close()

    def _end_cycle(self):
        """Release BLE, log, and emit the UI-restore signal."""
        if self._ble is not None:
            try:
                self._loop.run_until_complete(self._ble.disconnect())
            except Exception:
                pass
            self._ble = None
        self._current_client = None
        self.log_signal.emit("Cycle terminated. BLE disconnected.")
        self.cycle_done_signal.emit()

    # ── Client message handling ──────────────────────────────────

    def _handle_client(self, client, loop):
        client.settimeout(30.0)
        with client:
            while True:
                try:
                    data = client.recv(1024).decode('utf-8')
                    if not data:
                        break
                    msg = data.strip()
                    self.log_signal.emit(msg)
                    if msg.startswith("MEASURE|"):
                        self._handle_measure(client, loop, msg.split("|")[1])
                except socket.timeout:
                    self.log_signal.emit("30s timeout reached. Sequence finished.")
                    break
                except OSError:
                    # Socket error from reset_session()'s forced close() — normal shutdown.
                    break

    def _handle_measure(self, client, loop, loc):
        try:
            parts = loc.split('-')
            loc_converted = "-".join([str(int(p)) for p in parts])
            x, y = loop.run_until_complete(
                asyncio.wait_for(self._ble.read_level_data(), timeout=config.BLE_READ_TIMEOUT)
            )
            if x is None:
                raise ValueError("READ_ERROR")
            res = self._csv.write_row(loc_converted, x, y)
            if res:
                self.table_signal.emit(res)
        except Exception:
            self.log_signal.emit(f"BLE read failed at {loc}.")

    # ── Manual measurement ───────────────────────────────────────

    def _do_manual_read(self, loop):
        try:
            x, y = loop.run_until_complete(
                asyncio.wait_for(self._ble.read_level_data(), timeout=config.BLE_READ_TIMEOUT)
            )
            self.manual_result_signal.emit((x, y) if x is not None else None)
        except Exception:
            self.manual_result_signal.emit(None)


def _write_crash_log(text):
    try:
        with open("crash_log.txt", "a", encoding="utf-8") as f:
            f.write(f"\n=== CRASH {datetime.datetime.now()} ===\n")
            f.write(text)
    except Exception:
        pass
