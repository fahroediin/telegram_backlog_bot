import os
import threading
from flask import Flask, request
from dotenv import load_dotenv

# Impor kelas-kelas dari modul lain
from telegram_bot import TelegramBot
from google_sheets import GoogleSheetsClient
from converters.task_converter import process_telegram_text
from converters.backlog_converter import BacklogProcessor

# Muat semua variabel konfigurasi dari file .env
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID")
BOT_USERNAME = os.getenv("BOT_USERNAME")

# Lakukan validasi awal untuk memastikan semua konfigurasi ada
if not all([TELEGRAM_TOKEN, GEMINI_API_KEY, GOOGLE_SHEET_ID, WEBHOOK_URL, ADMIN_TELEGRAM_ID, BOT_USERNAME]):
    raise ValueError("Satu atau lebih variabel konfigurasi penting tidak ditemukan di file .env. Harap periksa kembali.")

# Inisialisasi semua komponen sistem
app = Flask(__name__)
bot = TelegramBot(token=TELEGRAM_TOKEN)
sheets_client = GoogleSheetsClient(credentials_file='credentials.json', spreadsheet_id=GOOGLE_SHEET_ID)
backlog_processor = BacklogProcessor(api_key=GEMINI_API_KEY)

def process_message_thread(data):
    """
    Fungsi ini menangani seluruh alur kerja di background thread
    agar server bisa langsung merespons webhook Telegram.
    """
    try:
        message = data['message']
        text = message.get('text', '')
        user_id_from_message = str(message['from']['id'])

        # Langkah 1: Validasi Keamanan - Pastikan hanya admin yang bisa memicu bot
        if user_id_from_message != ADMIN_TELEGRAM_ID:
            print(f"Akses ditolak untuk User ID: {user_id_from_message}. Hanya admin ({ADMIN_TELEGRAM_ID}) yang diizinkan.")
            return  # Hentikan proses jika bukan admin

        print(f"Akses diberikan untuk admin (User ID: {user_id_from_message}). Memulai proses...")

        # Langkah 2: Ekstrak teks mentah dari pesan Telegram
        lines = text.strip().split('\n')
        raw_text_lines = [line for line in lines if f"@{BOT_USERNAME}" not in line]
        raw_text = "\n".join(raw_text_lines)

        # Langkah 3: Panggil Task Converter untuk mengubah teks mentah menjadi data terstruktur awal
        intermediate_df = process_telegram_text(raw_text)
        if intermediate_df.empty:
            bot.send_message(ADMIN_TELEGRAM_ID, "Proses Gagal: Task Converter tidak menghasilkan data dari teks yang diberikan.")
            return

        # Langkah 4: Ambil konteks (daftar Epic yang sudah ada) dari Google Sheets
        existing_epics = sheets_client.get_existing_epics(worksheet_name='Backlog')

        # Langkah 5: Panggil Backlog Converter (LLM) dengan konteks Epic yang sudah ada
        final_df = backlog_processor.run_with_text(
            raw_text=intermediate_df.to_csv(sep='\t', index=False),
            existing_epics=existing_epics
        )
        if final_df is None or final_df.empty:
            bot.send_message(ADMIN_TELEGRAM_ID, "Proses Gagal: Backlog Converter (LLM) tidak menghasilkan data yang valid.")
            return
            
        # Langkah 6: Tambahkan data baru ke Google Sheets dan lakukan merge cell
        rows_added = sheets_client.append_and_merge_data(
            worksheet_name='Backlog', 
            data_df=final_df,
            merge_column_index=1  # 1 = Kolom A (Epic)
        )

        # Langkah 7: Kirim notifikasi sukses ke admin
        feedback_message = f"✅ Sukses! Berhasil menambahkan dan memformat {rows_added} task baru di Google Sheets dengan mempertimbangkan Epic yang sudah ada."
        bot.send_message(ADMIN_TELEGRAM_ID, feedback_message)

    except Exception as e:
        # Tangani error apa pun yang mungkin terjadi selama proses
        print(f"Error di thread pemrosesan: {e}")
        bot.send_message(ADMIN_TELEGRAM_ID, f"❌ Proses Gagal: Terjadi error.\n\nDetail: {e}")

@app.route('/webhook', methods=['POST'])
def telegram_webhook():
    """
    Endpoint ini menerima pembaruan dari Telegram (webhook).
    """
    data = request.get_json()
    # Cek apakah pesan valid dan mengandung mention ke bot
    if 'message' in data and 'text' in data['message']:
        text = data['message']['text']
        if BOT_USERNAME and f"@{BOT_USERNAME}" in text:
            # Jalankan proses utama di thread terpisah agar tidak memblokir Telegram
            thread = threading.Thread(target=process_message_thread, args=(data,))
            thread.start()
    
    # Selalu kembalikan 'OK' agar Telegram tahu pesannya sudah diterima
    return 'OK', 200

if __name__ == "__main__":
    # Atur webhook Telegram saat server pertama kali dijalankan
    # Pastikan WEBHOOK_URL di .env sudah benar
    print("Mengatur webhook Telegram...")
    bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    
    # Jalankan server Flask
    print("Server Flask siap menerima permintaan...")
    app.run(host='0.0.0.0', port=5001)