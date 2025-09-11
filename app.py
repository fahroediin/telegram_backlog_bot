import os
import threading
from flask import Flask, request
from dotenv import load_dotenv

from telegram_bot import TelegramBot
from google_sheets import GoogleSheetsClient
from converters.task_converter import process_telegram_text
from converters.backlog_converter import BacklogProcessor

load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID")
BOT_USERNAME = os.getenv("BOT_USERNAME")
WORKSHEET_NAME = os.getenv("TARGET_WORKSHEET_NAME", "Backlog")
# --- BACA KONFIGURASI SORTIR DARI .ENV ---
ENABLE_SORT = os.getenv("ENABLE_AUTO_SORT", "True").lower() == 'true'

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

        print(f"Akses diberikan untuk admin (User ID: {user_id_from_message}). Memulai proses...")

        lines = text.strip().split('\n')
        raw_text_lines = [line for line in lines if f"@{BOT_USERNAME}" not in line]
        raw_text = "\n".join(raw_text_lines)

        intermediate_df = process_telegram_text(raw_text)
        if intermediate_df.empty:
            bot.send_message(ADMIN_TELEGRAM_ID, f"Proses Gagal: Task Converter tidak menghasilkan data.")
            return

        existing_epics = sheets_client.get_existing_epics(worksheet_name=WORKSHEET_NAME)

        final_df = backlog_processor.run_with_text(
            raw_text=intermediate_df.to_csv(sep='\t', index=False),
            existing_epics=existing_epics
        )
        if final_df is None or final_df.empty:
            bot.send_message(ADMIN_TELEGRAM_ID, f"Proses Gagal: Backlog Converter (LLM) tidak menghasilkan data.")
            return
            
        # --- PANGGIL FUNGSI YANG LEBIH FLEKSIBEL ---
        rows_added = sheets_client.append_data(
            worksheet_name=WORKSHEET_NAME, 
            data_df=final_df,
            sort_enabled=ENABLE_SORT,
            primary_sort_col=5, # 5 = Kolom E (Start Date)
            secondary_sort_col=1  # 1 = Kolom A (Epic)
        )

        feedback_message = f"✅ Sukses! Berhasil menambahkan {rows_added} task baru ke worksheet '{WORKSHEET_NAME}'."
        if ENABLE_SORT:
            feedback_message += " Worksheet telah disortir berdasarkan tanggal."
        
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
    print(f"Sortir Otomatis: {'Aktif' if ENABLE_SORT else 'Nonaktif'}")
    app.run(host='0.0.0.0', port=5001)
