import asyncio
from bleak import BleakScanner, BleakClient
import config

class BleHandler:
    def __init__(self, address):
        self.address = address
        self.client = None

    async def connect(self):
        """기기와 연결을 시도하고 유지함"""
        if self.client is None or not self.client.is_connected:
            self.client = BleakClient(self.address, timeout=10.0)
            await self.client.connect()
        return True

    async def read_level_data(self):
        """연결된 상태에서 X, Y 데이터 읽기 [cite: 6]"""
        try:
            if self.client and self.client.is_connected:
                raw = await self.client.read_gatt_char(config.BLE_DATA_UUID)
                decoded = raw.decode('ascii')
                parts = decoded.split(':') # "4:0:X:Y" 형태 [cite: 6]
                if len(parts) >= 4:
                    return float(parts[2]), float(parts[3])
        except Exception:
            pass
        return None, None

    async def disconnect(self):
        if self.client and self.client.is_connected:
            await self.client.disconnect()

async def scan_devices():
    """제조사 필터링 조건에 맞는 기기 검색 [cite: 4]"""
    devices = await BleakScanner.discover(timeout=config.SCAN_TIMEOUT)
    found = []
    for d in devices:
        if d.name and len(d.name) > config.MIN_NAME_LENGTH:
            if d.name[:2] in config.FILTER_PREFIX:
                found.append(f"{d.name} ({d.address})")
    return found