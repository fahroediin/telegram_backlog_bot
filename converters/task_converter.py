# converters/task_converter.py
import pandas as pd
import re
from datetime import datetime, timedelta

def process_telegram_text(raw_text: str) -> pd.DataFrame:
    """
    Menerjemahkan logika dari Task Converter JavaScript ke Python.
    Mengubah teks mentah dari Telegram menjadi DataFrame terstruktur.
    """
    print("Memulai proses Task Converter (versi terjemahan dari JS)...")

    # --- Helper Functions (Terjemahan dari JS) ---
    month_map = {
        'januari': '01', 'februari': '02', 'maret': '03', 'april': '04', 
        'mei': '05', 'juni': '06', 'juli': '07', 'agustus': '08', 
        'september': '09', 'oktober': '10', 'november': '11', 'desember': '12'
    }

    def parse_date(date_string):
        try:
            parts = [p.strip() for p in date_string.split('-')]
            day = parts[0].zfill(2)
            month = month_map[parts[1].lower()]
            year = parts[2]
            return f"{year}-{month}-{day}"
        except (IndexError, KeyError):
            return None

    def summarize_task(full_description):
        delimiters = ['(', ',', ' untuk ', ' dengan detail', '(detail']
        best_index = -1
        for delimiter in delimiters:
            index = full_description.find(delimiter)
            if index != -1 and (best_index == -1 or index < best_index):
                best_index = index
        return full_description[:best_index].strip() if best_index != -1 else full_description

    # --- Logika Utama Parsing (Terjemahan dari JS) ---
    lines = raw_text.strip().split('\n')
    daily_tasks = {}
    current_date_iso = None
    current_pic = None

    for line in lines:
        trimmed_line = line.strip()
        if not trimmed_line or trimmed_line.startswith('='):
            continue

        date_match = re.match(r'^(\d{1,2})\s*-\s*([a-zA-Z]+)\s*-\s*(\d{4})$', trimmed_line)
        if date_match:
            current_date_iso = parse_date(trimmed_line)
            if current_date_iso and current_date_iso not in daily_tasks:
                daily_tasks[current_date_iso] = {}
            current_pic = None
            continue

        pic_match = re.match(r'^\d+\.\s*(.+)$', trimmed_line)
        if pic_match:
            current_pic = pic_match.group(1).strip()
            if current_date_iso and current_pic not in daily_tasks[current_date_iso]:
                daily_tasks[current_date_iso][current_pic] = []
            continue

        task_match = re.match(r'^-\s*(.+)$', trimmed_line)
        if task_match and current_date_iso and current_pic:
            daily_tasks[current_date_iso][current_pic].append(task_match.group(1).strip())

    # --- Logika Agregasi Task (Terjemahan dari JS) ---
    all_tasks = {}
    sorted_dates = sorted(daily_tasks.keys())

    for date in sorted_dates:
        for pic, tasks in daily_tasks[date].items():
            for task in tasks:
                task_key = f"{pic}:{task}"
                if task_key not in all_tasks:
                    all_tasks[task_key] = {'start_date': date, 'last_seen_date': date}
                else:
                    all_tasks[task_key]['last_seen_date'] = date

    # --- Logika Penentuan Status & End Date (Terjemahan dari JS) ---
    processed_data = []
    last_date = sorted_dates[-1] if sorted_dates else None

    for task_key, dates in all_tasks.items():
        pic, full_description = task_key.split(':', 1)
        start_date = dates['start_date']
        last_seen_date = dates['last_seen_date']
        
        short_task = summarize_task(full_description)
        status = 'InProgress'
        end_date = ''

        if last_date and last_seen_date < last_date:
            status = 'Done'
            try:
                # Cari tanggal berikutnya setelah last_seen_date
                last_seen_index = sorted_dates.index(last_seen_date)
                if last_seen_index + 1 < len(sorted_dates):
                    end_date_iso = sorted_dates[last_seen_index + 1]
                    end_date = datetime.strptime(end_date_iso, '%Y-%m-%d').strftime('%d %B %Y')
            except (ValueError, IndexError):
                pass # Biarkan end_date kosong jika terjadi error

        start_date_formatted = datetime.strptime(start_date, '%Y-%m-%d').strftime('%d %B %Y')

        processed_data.append([
            short_task,         # Judul Backlog
            full_description,   # Deskripsi Backlog
            pic,                # PIC
            status,             # Status
            start_date_formatted, # Start Date
            end_date            # End Date
        ])

    # --- Finalisasi ke DataFrame ---
    columns = ['Judul Backlog', 'Deskripsi Backlog', 'PIC', 'Status', 'Start Date', 'End Date']
    df = pd.DataFrame(processed_data, columns=columns)
    
    print(f"Task Converter selesai. Ditemukan {len(df)} task.")
    return df