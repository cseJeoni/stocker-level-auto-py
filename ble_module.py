import asyncio
from bleak import BleakScanner, BleakClient
import config

# EXE 빌드 시 WinRT 백엔드 의존성 누락 방지
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
    def __init__(self, address):
        self.address = address  # 레벨기의 MAC 주소
        self.client = None

    async def connect(self):
        if self.client is None or not self.client.is_connected:
            self.client = BleakClient(self.address, timeout=10.0)
            await self.client.connect()
        return True

    async def read_level_data(self):
        # 0.1초 간격으로 AVG_COUNT회 측정 후 X, Y 평균 반환
        x_list, y_list = [], []
        try:
            if not self.client or not self.client.is_connected:
                return None, None
            for _ in range(config.AVG_COUNT):
                raw = await self.client.read_gatt_char(config.BLE_DATA_UUID)
                parts = raw.decode('ascii').split(':')  # 예: "DATA:LEVEL:0.123:1.456"
                if len(parts) >= 4:
                    x_list.append(float(parts[2]))  # 2번째 자리 값이 X축
                    y_list.append(float(parts[3]))  # 3번째 자리 값이 Y축
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
    # 주변 블루투스 기기 검색 후 이름 필터링
    devices = await BleakScanner.discover(timeout=config.SCAN_TIMEOUT)
    return [
        f"{d.name} ({d.address})"
        for d in devices
        if d.name and len(d.name) > config.MIN_NAME_LENGTH and d.name[:2] in config.FILTER_PREFIX
    ]
