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

    def get_existing_epics(self, worksheet_name, epic_column_index=1):
        try:
            worksheet = self.spreadsheet.worksheet(worksheet_name)
            print(f"Membaca daftar Epic yang ada dari worksheet '{worksheet_name}'...")
            all_epics = worksheet.col_values(epic_column_index)
            existing_epics = sorted(list(set([epic for epic in all_epics[1:] if epic])))
            print(f"Ditemukan {len(existing_epics)} Epic unik.")
            return existing_epics
        except Exception as e:
            print(f"Error saat membaca Epic dari Google Sheets: {e}")
            return []

    def get_all_data_as_df(self, worksheet_name):
        """Membaca seluruh data dari worksheet dan mengembalikannya sebagai DataFrame Pandas."""
        try:
            worksheet = self.spreadsheet.worksheet(worksheet_name)
            print(f"Membaca seluruh data dari worksheet '{worksheet_name}'...")
            data = worksheet.get_all_records()
            df = pd.DataFrame(data)
            print(f"Berhasil membaca {len(df)} baris data.")
            return df
        except gspread.exceptions.WorksheetNotFound:
            print(f"Error: Worksheet '{worksheet_name}' tidak ditemukan.")
            return pd.DataFrame()
        except Exception as e:
            print(f"Error saat membaca seluruh data dari Google Sheets: {e}")
            return pd.DataFrame()

    def overwrite_worksheet_with_df(self, worksheet_name, data_df: pd.DataFrame):
        """Menghapus semua konten di worksheet dan menulis ulang dengan data dari DataFrame."""
        try:
            worksheet = self.spreadsheet.worksheet(worksheet_name)
            print(f"Menghapus dan menulis ulang worksheet '{worksheet_name}'...")
            
            # Hapus semua konten
            worksheet.clear()
            
            # Tulis ulang header dan data
            worksheet.update([data_df.columns.values.tolist()] + data_df.values.tolist(),
                              value_input_option='USER_ENTERED')
            
            print(f"Berhasil menulis ulang {len(data_df)} baris data.")
            return len(data_df)
        except Exception as e:
            print(f"Error saat menulis ulang worksheet: {e}")
            raise