import asyncio
from bleak import BleakScanner, BleakClient
import config

# Bleak's WinRT backend relies on several winrt sub-modules that PyInstaller's
# static analysis does not follow. Importing them explicitly here forces them
# into the frozen bundle and prevents a silent crash at runtime.
try:
    import winrt.windows.foundation
    import winrt.windows.foundation.collections
    import winrt.windows.devices.bluetooth
    import winrt.windows.devices.bluetooth.genericattributeprofile
    import winrt.windows.devices.enumeration
    import winrt.windows.devices.radios
    import winrt.windows.storage.streams
except ImportError:
    pass


class BleHandler:
    """Manages the BLE connection lifecycle and data retrieval for a single sensor device."""

    def __init__(self, address):
        self.address = address
        self.client = None

    async def connect(self):
        # Idempotent — skips re-initialization if the client is already connected.
        if self.client is None or not self.client.is_connected:
            self.client = BleakClient(self.address, timeout=10.0)
            await self.client.connect()
        return True

    async def read_level_data(self):
        # Collects AVG_COUNT samples at AVG_INTERVAL spacing to average out
        # sensor vibration noise, then returns the mean X/Y values rounded to 4 decimals.
        # Returns (None, None) on any BLE or parse error.
        # Expected GATT characteristic format: "DATA:LEVEL:<x>:<y>"
        x_list, y_list = [], []
        try:
            if not self.client or not self.client.is_connected:
                return None, None
            for _ in range(config.AVG_COUNT):
                raw = await self.client.read_gatt_char(config.BLE_DATA_UUID)
                parts = raw.decode('ascii').split(':')
                if len(parts) >= 4:
                    x_list.append(float(parts[2]))
                    y_list.append(float(parts[3]))
                await asyncio.sleep(config.AVG_INTERVAL)
            if x_list and y_list:
                return round(sum(x_list) / len(x_list), 4), round(sum(y_list) / len(y_list), 4)
        except Exception:
            pass
        return None, None

    async def disconnect(self):
        if self.client:
            await self.client.disconnect()


async def scan_devices():
    # Discovers nearby BLE devices and filters by name length and prefix
    # to return only compatible sensor models.
    devices = await BleakScanner.discover(timeout=config.SCAN_TIMEOUT)
    return [
        f"{d.name} ({d.address})"
        for d in devices
        if d.name and len(d.name) > config.MIN_NAME_LENGTH and d.name[:2] in config.FILTER_PREFIX
    ]
