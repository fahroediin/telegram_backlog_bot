# google_sheets.py
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd

class GoogleSheetsClient:
    def __init__(self, credentials_file, spreadsheet_id):
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name(credentials_file, scope)
        self.client = gspread.authorize(creds)
        self.spreadsheet = self.client.open_by_key(spreadsheet_id)
        print("Berhasil terhubung ke Google Sheets.")

    def append_data(self, worksheet_name, data_df: pd.DataFrame):
        try:
            worksheet = self.spreadsheet.worksheet(worksheet_name)
            # Mengubah NaN menjadi string kosong dan mengonversi DataFrame ke list of lists
            data_list = data_df.fillna('').values.tolist()
            worksheet.append_rows(data_list, value_input_option='USER_ENTERED')
            print(f"Berhasil menambahkan {len(data_list)} baris ke worksheet '{worksheet_name}'.")
            return len(data_list)
        except gspread.exceptions.WorksheetNotFound:
            print(f"Error: Worksheet dengan nama '{worksheet_name}' tidak ditemukan.")
            raise
        except Exception as e:
            print(f"Error saat menulis ke Google Sheets: {e}")
            raise