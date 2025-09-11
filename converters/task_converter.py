# converters/task_converter.py
import pandas as pd
import re
from datetime import datetime

def create_canonical_text(text: str) -> str:
    """Membersihkan teks untuk membuat kunci perbandingan yang andal."""
    if not isinstance(text, str):
        return ""
    return text.lower().strip()

def process_telegram_text(raw_text: str) -> pd.DataFrame:
    """
    HANYA mem-parsing teks laporan harian dari Telegram.
    Tidak lagi mencoba menentukan status atau melacak tanggal antar laporan.
    """
    print("Memulai proses Task Converter (logika disederhanakan)...")

    month_map = {
        'januari': 'January', 'februari': 'February', 'maret': 'March',
        'april': 'April', 'mei': 'May', 'juni': 'June',
        'juli': 'July', 'agustus': 'August', 'september': 'September',
        'oktober': 'October', 'november': 'November', 'desember': 'December'
    }

    def parse_date_to_string(date_string):
        """Mengubah '11 - September - 2025' menjadi '11 September 2025'."""
        try:
            parts = [p.strip() for p in date_string.split('-')]
            day = parts[0]
            month_name_id = parts[1].lower()
            month_name_en = month_map.get(month_name_id, month_name_id).capitalize()
            year = parts[2]
            return f"{day} {month_name_en} {year}"
        except (IndexError, KeyError):
            return None

    lines = raw_text.strip().split('\n')
    processed_data = []
    current_date_str = None
    current_pic = None

    for line in lines:
        trimmed_line = line.strip()
        if not trimmed_line or trimmed_line.startswith('='):
            continue

        date_match = re.match(r'^(\d{1,2})\s*-\s*([a-zA-Z]+)\s*-\s*(\d{4})$', trimmed_line)
        if date_match:
            current_date_str = parse_date_to_string(trimmed_line)
            continue

        pic_match = re.match(r'^\d+\.\s*(.+)$', trimmed_line)
        if pic_match:
            current_pic = pic_match.group(1).strip()
            continue

        task_match = re.match(r'^-\s*(.+)$', trimmed_line)
        if task_match and current_date_str and current_pic:
            full_description = task_match.group(1).strip()
            processed_data.append([
                full_description,
                create_canonical_text(full_description),
                current_pic,
                'InProgress',  # Status selalu InProgress untuk data baru
                current_date_str, # Gunakan tanggal yang sedang aktif
                ''             # End Date selalu kosong untuk data baru
            ])

    columns = ['Backlog', 'Canonical Backlog', 'PIC', 'Status', 'Start Date', 'End Date']
    df = pd.DataFrame(processed_data, columns=columns)
    
    print(f"Task Converter selesai. Ditemukan {len(df)} task.")
    return df