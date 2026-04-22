import csv
import os
from datetime import datetime
import config


class CSVHandler:
    """Creates and manages a session-scoped CSV file for recording shelf measurements."""

    def __init__(self, stocker_id):
        # The file is placed in the user's Downloads folder with a timestamp suffix
        # to prevent overwrites across multiple runs.
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        download_path = os.path.join(os.path.expanduser("~"), "Downloads")
        self.file_path = os.path.join(download_path, f"{stocker_id}_{timestamp}.csv")
        with open(self.file_path, 'w', newline='', encoding='euc-kr') as f:
            csv.writer(f).writerow(config.CSV_HEADER)

    def write_row(self, shelf_no, x, y):
        # Appends one measurement record. Returns the written row on success
        # (used to update the UI table), or None if the file write fails.
        row = [shelf_no, x, y]
        try:
            with open(self.file_path, 'a', newline='', encoding='euc-kr') as f:
                csv.writer(f).writerow(row)
            return row
        except Exception:
            return None
