# Telegram Backlog Bot

Otomatisasi Proses Grooming Backlog Harian dari Telegram ke Google Sheets Menggunakan AI.

Bot ini dirancang untuk mengubah laporan harian yang dikirim melalui grup Telegram menjadi baris data yang terstruktur rapi di dalam Google Sheets. Proses ini didukung oleh AI (Google Gemini) untuk mengkategorikan setiap tugas ke dalam Epic yang relevan secara otomatis.

---

## Daftar Isi
- [Gambaran Umum](#gambaran-umum)
- [Fitur Utama](#fitur-utama)
- [Arsitektur Sistem](#arsitektur-sistem)
- [Prasyarat](#prasyarat)
- [Langkah-langkah Instalasi](#langkah-langkah-instalasi)
- [Cara Menjalankan](#cara-menjalankan)
- [Struktur Proyek](#struktur-proyek)

---

## Gambaran Umum

Setiap hari, laporan tugas dikirim ke grup Telegram dalam format teks bebas. Proses manual untuk menyalin, memformat, mengkategorikan, dan memasukkan data ini ke Google Sheets memakan waktu dan rentan terhadap kesalahan.

Bot ini mengotomatiskan seluruh alur kerja tersebut:
1.  **Mendengarkan**: Bot akan aktif ketika di-mention di dalam grup Telegram.
2.  **Memproses**: Pesan teks mentah akan diproses oleh **Task Converter** untuk diubah menjadi format data awal (Judul, Deskripsi, PIC, Tanggal).
3.  **Menganalisis**: Data awal kemudian dikirim ke **Backlog Converter** yang menggunakan Google Gemini untuk menganalisis setiap tugas dan menetapkan **Epic** yang sesuai.
4.  **Menyimpan**: Data final yang sudah lengkap dengan Epic akan ditambahkan secara otomatis ke baris baru di Google Sheets.
5.  **Menggabungkan Sel**: Bot akan secara cerdas menggabungkan (merge) sel di kolom Epic untuk merapikan tampilan visual di Google Sheets.
6.  **Memberi Feedback**: Bot akan mengirim notifikasi pribadi ke admin untuk mengonfirmasi bahwa proses telah berhasil.

## Fitur Utama

-   ✅ **Otomatisasi Penuh**: Mengubah teks tidak terstruktur dari Telegram menjadi data terstruktur di Google Sheets tanpa intervensi manual.
-   ✅ **Kategorisasi Cerdas dengan AI**: Menggunakan Google Gemini untuk menetapkan Epic secara dinamis, baik menggunakan Epic yang sudah ada maupun membuat yang baru.
-   ✅ **Integrasi Real-time ke Google Sheets**: Data baru langsung ditambahkan ke bagian bawah spreadsheet, siap untuk dianalisis.
-   ✅ **Pemformatan Otomatis**: Secara otomatis menggabungkan sel Epic yang sama untuk visualisasi yang bersih dan rapi.
-   ✅ **Notifikasi Feedback Pribadi**: Memberikan konfirmasi sukses atau laporan error langsung ke admin melalui pesan pribadi.

## Arsitektur Sistem

-   **Antarmuka**: Bot Telegram
-   **Backend Server**: Aplikasi Flask (Python) yang berjalan sebagai webhook.
-   **Processing Core**:
    -   `Task Converter`: Modul Python untuk parsing awal teks Telegram.
    -   `Backlog Converter`: Modul Python yang terintegrasi dengan Google Gemini untuk kategorisasi Epic.
-   **Penyimpanan Data**: Google Sheets
-   **Konektor**:
    -   `python-telegram-bot` untuk komunikasi dengan Telegram API.
    -   `gspread` untuk komunikasi dengan Google Sheets API.

## Prasyarat

Sebelum memulai, pastikan Anda memiliki:
-   Python 3.8 atau lebih tinggi.
-   Akun Telegram.
-   Akun Google Cloud dengan penagihan (billing) aktif (untuk menghindari batas kuota API).
-   [Ngrok](https://ngrok.com/download) untuk development lokal.

## Langkah-langkah Instalasi

1.  **Clone Repository**
    ```bash
    git clone <URL_REPOSITORY_ANDA>
    cd telegram_backlog_bot
    ```

2.  **Buat Virtual Environment** (Sangat Direkomendasikan)
    ```bash
    python -m venv venv
    source venv/bin/activate  # Di Windows: venv\Scripts\activate
    ```

3.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Setup Kredensial**

    a. **Telegram**:
       - Buka Telegram dan cari **@BotFather**.
       - Buat bot baru dengan perintah `/newbot`.
       - Salin **Token API** yang diberikan.
       - Matikan mode privasi grup: `/mybots` -> pilih bot Anda -> `Bot Settings` -> `Group Privacy` -> `Turn off`.

    b. **Google Sheets & Drive API**:
       - Buka [Google Cloud Console](https://console.cloud.google.com/) dan buat proyek baru.
       - Aktifkan **Google Drive API** dan **Google Sheets API**.
       - Buat **Service Account**:
         - Di menu "Credentials", buat "Service Account". Beri peran **"Editor"**.
         - Setelah dibuat, masuk ke service account, klik tab "Keys" -> "Add Key" -> "Create new key".
         - Pilih **JSON** dan unduh filenya. **Ganti nama file ini menjadi `credentials.json`** dan letakkan di folder root proyek.
       - **Bagikan Google Sheet Anda**: Buka Google Sheet, klik "Share", dan bagikan dengan alamat email service account (terlihat seperti `...gserviceaccount.com`). Beri akses **"Editor"**.

    c. **Google Gemini API**:
       - Buka [Google AI Studio](https://aistudio.google.com/) dan dapatkan **API Key** Anda.

    d. **Telegram Admin ID**:
       - Buka Telegram dan cari **@userinfobot**.
       - Kirim `/start` untuk mendapatkan ID numerik Anda.

5.  **Konfigurasi File `.env`**
    -   Buat salinan dari `.env.example` dan beri nama `.env`.
    -   Buka file `.env` dan isi semua nilai yang diperlukan sesuai dengan kredensial yang telah Anda kumpulkan.

## Cara Menjalankan

1.  **Jalankan Ngrok**
    Buka terminal baru dan jalankan perintah ini untuk mengekspos port 5001 (port yang digunakan oleh Flask) ke internet.
    ```bash
    ngrok http 5001
    ```
    Ngrok akan memberikan URL `https` (misalnya: `https://1a2b-3c4d.ngrok-free.app`).

2.  **Update `.env`**
    -   Salin URL `https` dari Ngrok.
    -   Tempelkan ke variabel `WEBHOOK_URL` di dalam file `.env` Anda.

3.  **Jalankan Server Flask**
    Di terminal utama Anda (dengan virtual environment aktif), jalankan aplikasi:
    ```bash
    python app.py
    ```
    Server akan berjalan dan secara otomatis mengatur webhook Telegram.

4.  **Gunakan Bot di Telegram**
    -   Undang bot Anda ke grup Telegram yang diinginkan.
    -   Kirim pesan laporan harian Anda.
    -   Di akhir pesan, **mention bot Anda** (misal: `@NamaBotAnda`).
    -   Tunggu beberapa saat, dan Anda akan menerima notifikasi pribadi tentang hasilnya.

## Struktur Proyek

```
telegram_backlog_bot/
├── app.py                  # Server utama Flask, menangani webhook dan alur kerja.
├── telegram_bot.py         # Kelas untuk berinteraksi dengan Telegram API.
├── google_sheets.py        # Kelas untuk membaca/menulis data ke Google Sheets.
├── converters/             # Modul untuk logika pemrosesan teks.
│   ├── __init__.py
│   ├── task_converter.py   # Mengubah teks mentah Telegram menjadi data terstruktur awal.
│   └── backlog_converter.py# Menggunakan LLM untuk menambahkan Epic ke data.
├── credentials.json        # Kredensial Service Account Google (JANGAN DI-COMMIT).
├── requirements.txt        # Daftar library Python yang dibutuhkan.
├── .env                    # File konfigurasi untuk semua kredensial (JANGAN DI-COMMIT).
└── .env.example            # Template untuk file .env.
```