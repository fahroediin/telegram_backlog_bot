# google_sheets.py
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd

class GoogleSheetsClient:
    # ... (__init__ tetap sama) ...
    def __init__(self, credentials_file, spreadsheet_id):
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name(credentials_file, scope)
        self.client = gspread.authorize(creds)
        self.spreadsheet = self.client.open_by_key(spreadsheet_id)
        print("Berhasil terhubung ke Google Sheets.")

    # --- FUNGSI BARU UNTUK MEMBACA EPIC ---
    def get_existing_epics(self, worksheet_name, epic_column_index=1):
        """Membaca semua nilai di kolom Epic dan mengembalikan daftar unik."""
        try:
            worksheet = self.spreadsheet.worksheet(worksheet_name)
            print(f"Membaca daftar Epic yang ada dari worksheet '{worksheet_name}'...")
            # Mengambil semua nilai dari kolom pertama (Epic)
            all_epics = worksheet.col_values(epic_column_index)
            # Buang header ("Epic") dan nilai kosong, lalu buat daftar unik
            existing_epics = sorted(list(set([epic for epic in all_epics[1:] if epic])))
            print(f"Ditemukan {len(existing_epics)} Epic unik.")
            return existing_epics
        except gspread.exceptions.WorksheetNotFound:
            print(f"Error: Worksheet '{worksheet_name}' tidak ditemukan saat membaca Epic.")
            return []
        except Exception as e:
            print(f"Error saat membaca Epic dari Google Sheets: {e}")
            return []

    def append_and_merge_data(self, worksheet_name, data_df: pd.DataFrame, merge_column_index=1):
        """
        Menambahkan data ke worksheet dan kemudian menggabungkan sel di kolom yang ditentukan (berdasarkan Epic).
        Menggunakan notasi A1 untuk kompatibilitas maksimum.
        """
        try:
            worksheet = self.spreadsheet.worksheet(worksheet_name)
            
            start_row = len(worksheet.get_all_values()) + 1
            
            data_list = data_df.fillna('').values.tolist()
            if not data_list:
                print("Tidak ada data untuk ditambahkan.")
                return 0
                
            worksheet.append_rows(data_list, value_input_option='USER_ENTERED')
            print(f"Berhasil menambahkan {len(data_list)} baris baru.")

            # --- LOGIKA MERGE YANG DIPERBAIKI ---
            current_row = start_row
            epic_column_name = data_df.columns[0]
            
            for epic_name, group in data_df.groupby(epic_column_name, sort=False):
                num_rows_in_group = len(group)
                if num_rows_in_group > 1:
                    end_row = current_row + num_rows_in_group - 1
                    
                    # Menggunakan gspread.utils untuk mengubah nomor baris/kolom menjadi notasi A1
                    # Contoh: (376, 1) -> "A376"
                    start_cell = gspread.utils.rowcol_to_a1(current_row, merge_column_index)
                    end_cell = gspread.utils.rowcol_to_a1(end_row, merge_column_index)
                    range_to_merge = f"{start_cell}:{end_cell}"
                    
                    print(f"Menggabungkan sel untuk rentang: {range_to_merge}")
                    worksheet.merge_cells(range_to_merge, merge_type='MERGE_ROWS')
                
                current_row += num_rows_in_group

            print("Proses merge sel selesai.")
            return len(data_list)

        except gspread.exceptions.WorksheetNotFound:
            print(f"Error: Worksheet dengan nama '{worksheet_name}' tidak ditemukan.")
            raise
        except Exception as e:
            print(f"Error saat menulis atau menggabungkan sel di Google Sheets: {e}")
            raise