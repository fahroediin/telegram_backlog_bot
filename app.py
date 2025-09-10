# app.py
import os
import threading
from flask import Flask, request
from dotenv import load_dotenv

from telegram_bot import TelegramBot
from google_sheets import GoogleSheetsClient
from converters.task_converter import process_telegram_text
from converters.backlog_converter import BacklogProcessor

# Muat konfigurasi dari .env
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID") # ID Anda sudah ada di sini
BOT_USERNAME = os.getenv("BOT_USERNAME")

# Inisialisasi
app = Flask(__name__)
bot = TelegramBot(token=TELEGRAM_TOKEN)
sheets_client = GoogleSheetsClient(credentials_file='credentials.json', spreadsheet_id=GOOGLE_SHEET_ID)
backlog_processor = BacklogProcessor(api_key=GEMINI_API_KEY)

def process_message_thread(data):
    """Fungsi ini berjalan di background agar tidak memblokir webhook."""
    try:
        message = data['message']
        text = message.get('text', '')
        chat_id = message['chat']['id']
        user_id_from_message = str(message['from']['id']) # Ambil ID pengguna yang mengirim pesan

        # --- LANGKAH PREVENTIF: VALIDASI USER ID ---
        # Bandingkan ID pengirim dengan ID admin yang diizinkan dari file .env
        if user_id_from_message != ADMIN_TELEGRAM_ID:
            print(f"Akses ditolak untuk User ID: {user_id_from_message}. Hanya admin ({ADMIN_TELEGRAM_ID}) yang diizinkan.")
            # (Opsional) Kirim pesan penolakan ke pengguna yang tidak sah
            # bot.send_message(chat_id, f"Maaf, hanya admin yang dapat menggunakan bot ini.")
            return # Hentikan proses di sini

        print(f"Akses diberikan untuk admin (User ID: {user_id_from_message}). Memulai proses...")

        # 1. Ekstrak teks mentah (buang baris mention)
        lines = text.strip().split('\n')
        raw_text_lines = [line for line in lines if f"@{BOT_USERNAME}" not in line]
        raw_text = "\n".join(raw_text_lines)

        # 2. Panggil Task Converter
        intermediate_df = process_telegram_text(raw_text)
        if intermediate_df.empty:
            bot.send_message(ADMIN_TELEGRAM_ID, "Proses Gagal: Task Converter tidak menghasilkan data.")
            return

        # 3. Panggil Backlog Converter
        final_df = backlog_processor.run_with_text(intermediate_df.to_csv(sep='\t', index=False))
        if final_df is None or final_df.empty:
            bot.send_message(ADMIN_TELEGRAM_ID, "Proses Gagal: Backlog Converter (LLM) tidak menghasilkan data.")
            return
            
        # 4. Tambahkan dan Merge di Google Sheets
        rows_added = sheets_client.append_and_merge_data(
            worksheet_name='Backlog', 
            data_df=final_df,
            merge_column_index=1
        )

        # 5. Kirim feedback
        feedback_message = f"✅ Sukses! Berhasil menambahkan dan memformat {rows_added} task baru di Google Sheets."
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
    bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    app.run(host='0.0.0.0', port=5001)