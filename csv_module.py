import csv
import os
from datetime import datetime
import config

class CSVHandler:
    def __init__(self, stocker_id):
        self.stocker_id = stocker_id

        # 사용자의 '다운로드' 폴더 경로를 자동으로 추적
        download_path = os.path.join(os.path.expanduser("~"), "Downloads")
        # 파일명 중복 방지를 위한 타임스탬프
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 다운로드 폴더에 파일 생성
        self.file_path = os.path.join(download_path, f"{self.stocker_id}_{timestamp}.csv")
        self._create_file()

    def _create_file(self):
        # 새로운 CSV 파일을 생성하고 첫 줄에 헤더를 작성 
        with open(self.file_path, 'w', newline='', encoding='euc-kr') as f:
            writer = csv.writer(f)
            writer.writerow(config.CSV_HEADER)

    def write_row(self, shelf_no, x, y):
        row = [shelf_no, x, y]
        try:
            # append 모드로 열어 기존 데이터를 보존하면서 새 데이터를 추가 
            with open(self.file_path, 'a', newline='', encoding='euc-kr') as f:
                writer = csv.writer(f)
                writer.writerow(row)
            return row
        except Exception:
            return None