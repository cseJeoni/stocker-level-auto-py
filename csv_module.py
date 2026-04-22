import csv
import os
from datetime import datetime
import config


class CSVHandler:
    def __init__(self, stocker_id):
        # 사용자의 '다운로드' 폴더에 타임스탬프 포함 파일명으로 생성 (중복 방지)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        download_path = os.path.join(os.path.expanduser("~"), "Downloads")
        self.file_path = os.path.join(download_path, f"{stocker_id}_{timestamp}.csv")
        with open(self.file_path, 'w', newline='', encoding='euc-kr') as f:
            csv.writer(f).writerow(config.CSV_HEADER)

    def write_row(self, shelf_no, x, y):
        row = [shelf_no, x, y]
        try:
            # append 모드로 열어 기존 데이터를 보존하면서 새 데이터를 추가
            with open(self.file_path, 'a', newline='', encoding='euc-kr') as f:
                csv.writer(f).writerow(row)
            return row
        except Exception:
            return None
