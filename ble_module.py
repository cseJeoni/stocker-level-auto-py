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
        self.address = address # 레벨기의 MAC 주소
        self.client = None

    async def connect(self):
        # 블루투스 기기와 연결을 시도 
        if self.client is None or not self.client.is_connected:
            self.client = BleakClient(self.address, timeout=10.0)
            await self.client.connect()
        return True

    async def read_level_data(self):
        # 데이터 필터링 및 평균화 
        x_list, y_list = [], []
        try:
            if not self.client or not self.client.is_connected: return None, None

            for _ in range(config.AVG_COUNT):
                # 레벨기에서 Raw 데이터 (아스키코드)를 읽어옴 
                raw = await self.client.read_gatt_char(config.BLE_DATA_UUID)
                decoded = raw.decode('ascii')
                parts = decoded.split(':') # 예: "DATA:LEVEL:0.123:1.456" 을 콜론 기준으로 쪼갬

                if len(parts) >= 4:
                    x_list.append(float(parts[2])) # 리스트에서 2번째 자리 값이 X축 
                    y_list.append(float(parts[3])) # 리스트에서 3번째 자리 값이 Y축 
                await asyncio.sleep(config.AVG_INTERVAL) # 0.1초 대기 후 다시 측정 

            # 리스트에 모인 5개 값을 더해서 5로 나누고, 소수점 4자리까지 반올림
            if x_list and y_list:
                return round(sum(x_list)/len(x_list), 4), round(sum(y_list)/len(y_list), 4)
        except Exception: pass
        return None, None

    async def disconnect(self):
        # 블루투스 연결 해제 
        if self.client: await self.client.disconnect()

async def scan_devices():
    # 주변의 블루투스 기기 검색 
    devices = await BleakScanner.discover(timeout=config.SCAN_TIMEOUT)
    found = []
    for d in devices:
        if d.name and len(d.name) > config.MIN_NAME_LENGTH:
            if d.name[:2] in config.FILTER_PREFIX:
                found.append(f"{d.name} ({d.address})")
    return found