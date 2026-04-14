import asyncio
from bleak import BleakScanner, BleakClient
import config

class BleHandler:
    def __init__(self, address):
        self.address = address
        self.client = None

    async def connect(self):
        """레벨기와 상시 연결 유지"""
        if self.client is None or not self.client.is_connected:
            self.client = BleakClient(self.address, timeout=10.0)
            await self.client.connect()
        return True

    async def read_level_data(self):
        """평균값 산출 로직: 여러 번 읽어 평균 리턴"""
        x_list, y_list = [], []
        try:
            if not self.client or not self.client.is_connected:
                return None, None

            for _ in range(config.AVG_COUNT):
                raw = await self.client.read_gatt_char(config.BLE_DATA_UUID)
                decoded = raw.decode('ascii')
                parts = decoded.split(':') # "4:0:X:Y"
                if len(parts) >= 4:
                    x_list.append(float(parts[2]))
                    y_list.append(float(parts[3]))
                await asyncio.sleep(config.AVG_INTERVAL)

            if x_list and y_list:
                return round(sum(x_list)/len(x_list), 4), round(sum(y_list)/len(y_list), 4)
        except Exception:
            pass
        return None, None

    async def disconnect(self):
        if self.client: await self.client.disconnect()

async def scan_devices():
    """조건에 맞는 장치 검색"""
    devices = await BleakScanner.discover(timeout=config.SCAN_TIMEOUT)
    found = []
    for d in devices:
        if d.name and len(d.name) > config.MIN_NAME_LENGTH:
            if d.name[:2] in config.FILTER_PREFIX:
                found.append(f"{d.name} ({d.address})")
    return found