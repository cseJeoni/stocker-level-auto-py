import os
import xlwings as xw
import config

class ExcelHandler:
    def __init__(self, file_path):
        self.file_path = file_path.replace('/', '\\')

    def write_to_active_sheet(self, location, x_val, y_val):
        """ActiveSheet에서 위치 찾아 기록"""
        try:
            app = xw.apps.active if xw.apps.count > 0 else xw.App(visible=True)
            target_name = os.path.basename(self.file_path)
            book = next((b for b in app.books if b.name == target_name), None)
            if not book: book = app.books.open(self.file_path)
            
            ws = book.sheets.active
            last_row = ws.range('C' + str(ws.cells.last_cell.row)).end('up').row
            if last_row < config.XL_START_ROW: last_row = 100
            
            b1_data = ws.range((config.XL_START_ROW, config.XL_B1_SHELF), (last_row, config.XL_B1_SHELF)).value
            b2_data = ws.range((config.XL_START_ROW, config.XL_B2_SHELF), (last_row, config.XL_B2_SHELF)).value

            for data, s_col, x_col, y_col in [
                (b1_data, config.XL_B1_SHELF, config.XL_B1_X, config.XL_B1_Y),
                (b2_data, config.XL_B2_SHELF, config.XL_B2_X, config.XL_B2_Y)
            ]:
                if data:
                    for i, val in enumerate(data):
                        if val and str(val).strip() == location:
                            row = config.XL_START_ROW + i
                            ws.cells(row, x_col).value = x_val
                            ws.cells(row, y_col).value = y_val
                            return True
            return False
        except Exception:
            return False