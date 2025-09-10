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

    def append_and_sort_data(self, worksheet_name, data_df: pd.DataFrame, sort_column_index=1, secondary_sort_column_index=5):
        """
        Menambahkan data ke worksheet dan kemudian MENSORTIR seluruh sheet
        berdasarkan kolom utama (Epic) dan kolom sekunder (Start Date).
        """
        try:
            worksheet = self.spreadsheet.worksheet(worksheet_name)
            
            # 1. Tambahkan data baru di akhir
            data_list = data_df.fillna('').values.tolist()
            if not data_list:
                print("Tidak ada data untuk ditambahkan.")
                return 0
                
            worksheet.append_rows(data_list, value_input_option='USER_ENTERED')
            print(f"Berhasil menambahkan {len(data_list)} baris baru.")

            # 2. Kirim perintah untuk mensortir seluruh sheet
            # Dapatkan jumlah total baris untuk menentukan rentang sortir
            total_rows = len(worksheet.get_all_values())
            if total_rows > 1:
                print(f"Mensortir worksheet berdasarkan kolom {sort_column_index} (Epic) dan {secondary_sort_column_index} (Start Date)...")
                
                # Tentukan rentang dari A2 hingga kolom terakhir dan baris terakhir
                last_column_letter = gspread.utils.rowcol_to_a1(1, worksheet.col_count)[0]
                sort_range = f'A2:{last_column_letter}{total_rows}'
                
                worksheet.sort(
                    (sort_column_index, 'asc'), 
                    (secondary_sort_column_index, 'asc'), 
                    range=sort_range
                )
            
            print("Proses penambahan dan sortir selesai.")
            return len(data_list)

        except gspread.exceptions.WorksheetNotFound:
            print(f"Error: Worksheet dengan nama '{worksheet_name}' tidak ditemukan.")
            raise
        except Exception as e:
            print(f"Error saat menulis atau mensortir di Google Sheets: {e}")
            raise