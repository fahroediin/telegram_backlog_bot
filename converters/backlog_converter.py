import os
import pandas as pd
import io
import google.generativeai as genai
import re

def convert_indonesian_date(date_str: str) -> str | None:
    if not isinstance(date_str, str) or not date_str.strip():
        return None
    month_map_id_to_en = {
        'januari': 'January', 'februari': 'February', 'maret': 'March',
        'april': 'April', 'mei': 'May', 'juni': 'June',
        'juli': 'July', 'agustus': 'August', 'september': 'September',
        'oktober': 'October', 'november': 'November', 'desember': 'December'
    }
    try:
        parts = date_str.lower().split()
        if len(parts) == 3:
            day, month_id, year = parts
            month_en = month_map_id_to_en.get(month_id)
            if month_en:
                return f"{day} {month_en} {year}"
    except Exception:
        pass
    return date_str

class BacklogProcessor:
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("API Key tidak ditemukan.")
        genai.configure(api_key=api_key)

    # --- PROMPT DISEMPURNAKAN DENGAN CONTOH ---
    def _create_prompt(self, raw_backlog_text: str) -> str:
        prompt = f"""
        Anda adalah seorang Agile Project Manager yang sangat ahli dalam melakukan backlog grooming.
        Tugas Anda adalah menganalisis daftar backlog mentah berikut dan mengelompokkannya ke dalam Epic yang logis dan spesifik, meniru gaya pada contoh yang diberikan.

        FORMAT INPUT:
        Setiap baris dalam backlog mentah memiliki 6 kolom yang dipisahkan oleh karakter TAB.
        Formatnya adalah: Judul Backlog<TAB>Deskripsi Backlog<TAB>PIC<TAB>Status<TAB>Start Date<TAB>End Date.

        ATURAN PENTING:
        1.  **Identifikasi Epic**: Berdasarkan 'Deskripsi Backlog', tentukan nama Epic yang paling relevan. Gunakan nama Epic yang konsisten untuk tugas-tugas yang mirip. Pelajari gaya penamaan Epic dari contoh di bawah.
        2.  **Gabungkan Backlog**: Di kolom output 'Backlog', gabungkan 'Judul Backlog' dan 'Deskripsi Backlog' dari input. Formatnya harus: "Judul Backlog: Deskripsi Backlog".
        3.  **Ekstraksi Akurat**: Ekstrak kolom PIC, Status, Start Date, dan End Date dengan benar.
        4.  **Format Output**: Hasil akhir HARUS berupa teks dengan format CSV, menggunakan pemisah pipa '|'. Jangan tambahkan teks pembuka atau penutup apa pun, hanya data CSV murni.
        5.  **Kolom Output**: Urutan kolom harus persis seperti ini (6 kolom): Epic|Backlog|PIC|Status|Start Date|End Date

        CONTOH:
        Jika inputnya adalah:
        `Update status via losfunction (mobile)	kemudian update status dengan menggunakan fungsi losfunction > Folder History > DoUpdateHistoryAndSetCurrentState	Jody	Done	11 Juni 2025	13 Juni 2025`
        `Audit trail Apply Loan Now	Audit trail Apply Loan Now Preview data hanya di new data, old data kosong	Sandi	Done	11 Juni 2025	12 Juni 2025`
        `Add field interest type	add field interest type di master product	Stella	Done	12 Juni 2025	13 Juni 2025`

        Maka output yang diharapkan adalah:
        `Mobile Enhancements|Update status dengan menggunakan fungsi losfunction > Folder History > DoUpdateHistoryAndSetCurrentState|Jody|Done|11 Juni 2025|13 Juni 2025`
        `Audit Trail|Audit trail Apply Loan Now Preview data hanya di new data, old data kosong|Sandi|Done|11 Juni 2025|12 Juni 2025`
        `Master Data & Product|add field interest type di master product|Stella|Done|12 Juni 2025|13 Juni 2025`
        ---

        Berikut adalah daftar backlog mentah yang harus Anda proses:
        --- BACKLOG MENTAH ---
        {raw_backlog_text}
        --- AKHIR BACKLOG MENTAH ---

        Sekarang, proses backlog di atas dan hasilkan output dalam format CSV dengan pemisah pipa '|' sesuai aturan.
        """
        return prompt

    def process_with_llm(self, raw_backlog_text: str) -> str:
        prompt = self._create_prompt(raw_backlog_text)
        print("Mengirim permintaan ke Google Gemini...")
        try:
            model = genai.GenerativeModel('gemini-2.5-flash') 
            generation_config = {"temperature": 0.1}
            safety_settings = {'HATE': 'block_none', 'HARASSMENT': 'block_none', 'SEXUAL' : 'block_none', 'DANGEROUS' : 'block_none'}
            response = model.generate_content(prompt, generation_config=generation_config, safety_settings=safety_settings)
            print("Respons dari Gemini diterima.")
            return response.text.strip()
        except Exception as e:
            print(f"Terjadi error saat menghubungi API Gemini: {e}")
            return ""

    # --- PARSER TETAP SAMA, KARENA OUTPUT YANG DIHARAPKAN TETAP 5 KOLOM ---
    def _parse_llm_response(self, llm_response: str) -> pd.DataFrame:
        if not llm_response:
            print("Respons LLM kosong.")
            return pd.DataFrame()

        cleaned_response = re.sub(r'```(csv)?', '', llm_response)
        lines = cleaned_response.strip().split('\n')
        
        header_str = "Epic|Backlog|PIC|Status|Start Date|End Date"
        expected_columns = header_str.split('|')
        num_separators = len(expected_columns) - 1

        data_lines = [line.strip() for line in lines if line.count('|') == num_separators]

        if not data_lines:
            print("Tidak ada baris data valid yang ditemukan dalam respons LLM.")
            print("--- Respons Mentah dari LLM ---")
            print(llm_response)
            print("-------------------------------")
            return pd.DataFrame()

        csv_data_to_parse = "\n".join(data_lines)
        data = io.StringIO(csv_data_to_parse)
        
        try:
            df = pd.read_csv(data, sep='|', header=None, names=expected_columns)
            for col in df.columns:
                if df[col].dtype == 'object':
                    df[col] = df[col].astype(str).str.strip()
            
            print("Respons LLM berhasil diurai menjadi tabel.")
            return df
        except Exception as e:
            print(f"Gagal mengurai respons LLM. Error: {e}")
            return pd.DataFrame()

    def run_with_text(self, raw_text: str) -> pd.DataFrame | None:
        llm_result = self.process_with_llm(raw_text)
        if not llm_result: return None
        structured_data = self._parse_llm_response(llm_result)
        if structured_data.empty: return None
        
        if 'Start Date' in structured_data.columns:
            structured_data['Start Date'] = structured_data['Start Date'].apply(convert_indonesian_date)
            structured_data['Start Date'] = pd.to_datetime(structured_data['Start Date'], errors='coerce')
        if 'End Date' in structured_data.columns:
            structured_data['End Date'] = structured_data['End Date'].apply(convert_indonesian_date)
            structured_data['End Date'] = pd.to_datetime(structured_data['End Date'], errors='coerce')

        structured_data = structured_data.sort_values(by=['Epic', 'Start Date'], ascending=[True, True], na_position='last')
        
        structured_data.fillna('', inplace=True)

        if 'Start Date' in structured_data.columns:
            structured_data['Start Date'] = structured_data['Start Date'].apply(lambda x: x.strftime('%d %B %Y') if pd.notna(x) and x != '' else '')
        if 'End Date' in structured_data.columns:
            structured_data['End Date'] = structured_data['End Date'].apply(lambda x: x.strftime('%d %B %Y') if pd.notna(x) and x != '' else '')

        return structured_data