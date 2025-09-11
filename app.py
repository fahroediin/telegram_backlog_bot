import os
import threading
from flask import Flask, request
from dotenv import load_dotenv
import pandas as pd
from datetime import datetime

from telegram_bot import TelegramBot
from google_sheets import GoogleSheetsClient
from converters.task_converter import process_telegram_text, create_canonical_text
from converters.backlog_converter import BacklogProcessor, convert_mixed_language_date

load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID")
BOT_USERNAME = os.getenv("BOT_USERNAME")
WORKSHEET_NAME = os.getenv("TARGET_WORKSHEET_NAME", "Backlog")

if not all([TELEGRAM_TOKEN, GEMINI_API_KEY, GOOGLE_SHEET_ID, WEBHOOK_URL, ADMIN_TELEGRAM_ID, BOT_USERNAME, WORKSHEET_NAME]):
    raise ValueError("Satu atau lebih variabel konfigurasi penting tidak ditemukan di file .env.")

app = Flask(__name__)
bot = TelegramBot(token=TELEGRAM_TOKEN)
sheets_client = GoogleSheetsClient(credentials_file='credentials.json', spreadsheet_id=GOOGLE_SHEET_ID)
backlog_processor = BacklogProcessor(api_key=GEMINI_API_KEY)

def process_message_thread(data):
    try:
        message = data['message']
        text = message.get('text', '')
        user_id_from_message = str(message['from']['id'])

        if user_id_from_message != ADMIN_TELEGRAM_ID:
            print(f"Akses ditolak untuk User ID: {user_id_from_message}.")
            return

        print(f"Akses diberikan untuk admin. Memulai proses update status...")

        # 1. BACA DATA DAN BERSIHKAN
        existing_df = sheets_client.get_all_data_as_df(worksheet_name=WORKSHEET_NAME)
        if not existing_df.empty:
            required_cols = ['Epic', 'Backlog', 'PIC', 'Status', 'Start Date', 'End Date']
            for col in required_cols:
                if col not in existing_df.columns:
                    raise KeyError(f"Kolom '{col}' tidak ditemukan di Google Sheet.")
            
            existing_df['Start Date'] = existing_df['Start Date'].apply(convert_mixed_language_date).pipe(pd.to_datetime, errors='coerce')
            existing_df['End Date'] = existing_df['End Date'].apply(convert_mixed_language_date).pipe(pd.to_datetime, errors='coerce')
            existing_df['Canonical Backlog'] = existing_df['Backlog'].apply(create_canonical_text)
            existing_df.drop_duplicates(subset=['PIC', 'Canonical Backlog'], keep='last', inplace=True)

        done_tasks_df = existing_df[existing_df['Status'] == 'Done'].copy().reset_index(drop=True)
        inprogress_tasks_df = existing_df[existing_df['Status'] == 'InProgress'].copy().reset_index(drop=True)

        # 2. PROSES INPUT BARU DARI TELEGRAM
        lines = text.strip().split('\n')
        raw_text_lines = [line for line in lines if f"@{BOT_USERNAME}" not in line]
        raw_text = "\n".join(raw_text_lines)
        
        intermediate_df = process_telegram_text(raw_text)
        if intermediate_df.empty:
            bot.send_message(ADMIN_TELEGRAM_ID, "Proses Gagal: Task Converter tidak menghasilkan data.")
            return

        if not intermediate_df.empty:
            intermediate_df.drop_duplicates(subset=['PIC', 'Canonical Backlog'], keep='first', inplace=True)

        # 3. DAPATKAN EPIC UNTUK TASK BARU (SATU PER SATU UNTUK KEANDALAN MAKSIMAL)
        existing_epics = list(existing_df['Epic'].unique()) if not existing_df.empty else []
        
        all_processed_tasks = []
        for index, row in intermediate_df.iterrows():
            single_task_df = pd.DataFrame([row])
            print(f"Memproses task: {row['Backlog'][:50]}...")
            
            processed_task = backlog_processor.get_epics_for_new_tasks(
                intermediate_df=single_task_df,
                existing_epics=existing_epics
            )
            
            if processed_task is not None and not processed_task.empty:
                all_processed_tasks.append(processed_task)
            else:
                print(f"Peringatan: Gagal memproses task tunggal. Melanjutkan...")

        if not all_processed_tasks:
            bot.send_message(ADMIN_TELEGRAM_ID, "Proses Gagal: Backlog Converter (LLM) tidak menghasilkan data valid untuk semua task.")
            return
            
        new_tasks_with_epics_df = pd.concat(all_processed_tasks, ignore_index=True)

        # 4. LOGIKA PERBANDINGAN MENGGUNAKAN KUNCI KANONIS
        inprogress_tasks_df['task_key'] = inprogress_tasks_df['PIC'].astype(str) + ' | ' + inprogress_tasks_df['Canonical Backlog'].astype(str)
        new_tasks_with_epics_df['task_key'] = new_tasks_with_epics_df['PIC'].astype(str) + ' | ' + new_tasks_with_epics_df['Canonical Backlog'].astype(str)

        merged_df = pd.merge(
            inprogress_tasks_df, new_tasks_with_epics_df,
            on='task_key', how='outer', suffixes=('_old', '_new'), indicator=True
        ).reset_index(drop=True)

        tasks_to_keep = []
        today = datetime.now()

        # A. Task yang selesai
        completed_tasks_slice = merged_df[merged_df['_merge'] == 'left_only']
        if not completed_tasks_slice.empty:
            completed = completed_tasks_slice[[c for c in merged_df.columns if c.endswith('_old')]].copy()
            completed.columns = [c.replace('_old', '') for c in completed.columns]
            completed['Status'] = 'Done'
            completed['End Date'] = today
            tasks_to_keep.append(completed)

        # B. Task yang masih berjalan
        ongoing_tasks_slice = merged_df[merged_df['_merge'] == 'both']
        if not ongoing_tasks_slice.empty:
            ongoing = ongoing_tasks_slice[[c for c in merged_df.columns if c.endswith('_old')]].copy()
            ongoing.columns = [c.replace('_old', '') for c in ongoing.columns]
            tasks_to_keep.append(ongoing)

        # C. Task yang benar-benar baru
        brand_new_tasks_slice = merged_df[merged_df['_merge'] == 'right_only']
        if not brand_new_tasks_slice.empty:
            brand_new = brand_new_tasks_slice[[c for c in merged_df.columns if c.endswith('_new')]].copy()
            brand_new.columns = [c.replace('_new', '') for c in brand_new.columns]
            tasks_to_keep.append(brand_new)

        # 5. GABUNGKAN SEMUA DATA
        if tasks_to_keep:
            final_inprogress_df = pd.concat(tasks_to_keep, ignore_index=True)
            final_df = pd.concat([done_tasks_df, final_inprogress_df], ignore_index=True)
        else:
            final_df = done_tasks_df.copy()

        final_df = final_df.drop(columns=['task_key', '_merge', 'Canonical Backlog'], errors='ignore')
        final_df = final_df[required_cols]

        # 6. SORTIR DAN FORMAT ULANG TANGGAL
        final_df['Start Date'] = pd.to_datetime(final_df['Start Date'], errors='coerce')
        final_df['End Date'] = pd.to_datetime(final_df['End Date'], errors='coerce')
        
        final_df = final_df.sort_values(by=['Start Date', 'Epic'], ascending=[True, True], na_position='last')
        
        final_df['Start Date'] = final_df['Start Date'].dt.strftime('%d %B %Y').fillna('')
        final_df['End Date'] = final_df['End Date'].dt.strftime('%d %B %Y').fillna('')
        
        # 7. TULIS ULANG SELURUH WORKSHEET
        rows_updated = sheets_client.overwrite_worksheet_with_df(
            worksheet_name=WORKSHEET_NAME, 
            data_df=final_df
        )

        feedback_message = f"✅ Sukses! Worksheet '{WORKSHEET_NAME}' telah di-update. Total {rows_updated} baris data."
        bot.send_message(ADMIN_TELEGRAM_ID, feedback_message)

    except Exception as e:
        print(f"Error di thread pemrosesan: {e}")
        bot.send_message(ADMIN_TELEGRAM_ID, f"❌ Proses Gagal: Terjadi error.\n\nDetail: {e}")

@app.route('/webhook', methods=['POST'])
def telegram_webhook():
    data = request.get_json()
    if 'message' in data and 'text' in data['message']:
        text = data['message']['text']
        if BOT_USERNAME and f"@{BOT_USERNAME}" in text:
            thread = threading.Thread(target=process_message_thread, args=(data,))
            thread.start()
    return 'OK', 200

if __name__ == "__main__":
    print("Mengatur webhook Telegram...")
    bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    print(f"Server Flask siap menerima permintaan untuk worksheet: '{WORKSHEET_NAME}'")
    app.run(host='0.0.0.0', port=5001)