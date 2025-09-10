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
ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID")
BOT_USERNAME = os.getenv("BOT_USERNAME") # Tambahkan username bot Anda di .env

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
        user_id = message['from']['id']
        
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
            
        # 4. Tambahkan ke Google Sheets
        rows_added = sheets_client.append_data(worksheet_name='Backlog', data_df=final_df)

        # 5. Kirim feedback
        feedback_message = f"✅ Sukses! Berhasil menambahkan {rows_added} task baru ke Google Sheets."
        bot.send_message(ADMIN_TELEGRAM_ID, feedback_message)

    except Exception as e:
        print(f"Error di thread pemrosesan: {e}")
        bot.send_message(ADMIN_TELEGRAM_ID, f"❌ Proses Gagal: Terjadi error.\n\nDetail: {e}")

@app.route('/webhook', methods=['POST'])
def telegram_webhook():
    data = request.get_json()
    if 'message' in data and 'text' in data['message']:
        text = data['message']['text']
        # Cek apakah bot di-mention
        if BOT_USERNAME and f"@{BOT_USERNAME}" in text:
            # Jalankan proses di thread terpisah
            thread = threading.Thread(target=process_message_thread, args=(data,))
            thread.start()
    return 'OK', 200

if __name__ == "__main__":
    # Atur webhook saat server pertama kali dijalankan
    bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    app.run(host='0.0.0.0', port=5001)