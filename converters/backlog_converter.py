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

    # --- PROMPT SEKARANG MENERIMA KONTEKS ---
    def _create_prompt(self, raw_backlog_text: str, existing_epics: list[str]) -> str:
        # Ubah daftar Epic menjadi string yang mudah dibaca
        epics_list_str = ", ".join(f'"{epic}"' for epic in existing_epics)

        prompt = f"""
        Anda adalah seorang Agile Project Manager yang sangat ahli dan konsisten.
        Tugas Anda adalah menganalisis backlog baru dan menetapkan Epic untuk setiap item.

        KONTEKS PENTING:
        Berikut adalah daftar Epic yang SUDAH ADA di dalam spreadsheet:
        [{epics_list_str}]

        ATURAN UTAMA:
        1.  **GUNAKAN KEMBALI EPIC YANG ADA**: Untuk setiap backlog, pertama-tama periksa apakah topiknya cocok dengan salah satu Epic yang sudah ada di daftar di atas. Jika cocok, HARUS gunakan nama Epic yang persis sama. Contoh: Jika ada Epic "Refactor", gunakan itu, jangan membuat "Code Refactoring".
        2.  **BUAT EPIC BARU JIKA PERLU**: Hanya jika sebuah backlog memiliki topik yang benar-benar baru dan tidak cocok dengan Epic mana pun yang ada, Anda boleh membuat nama Epic baru yang singkat dan deskriptif.
        3.  **Gabungkan Backlog**: Di kolom output 'Backlog', gabungkan 'Judul Backlog' dan 'Deskripsi Backlog' dari input. Formatnya: "Judul Backlog: Deskripsi Backlog".
        4.  **Format Output**: Hasil akhir HARUS berupa teks CSV dengan pemisah pipa '|', tanpa teks pembuka/penutup.
        5.  **Kolom Output**: Urutan kolom harus: Epic|Backlog|PIC|Status|Start Date|End Date

        FORMAT INPUT:
        Setiap baris input dipisahkan oleh TAB: Judul Backlog<TAB>Deskripsi Backlog<TAB>PIC<TAB>Status<TAB>Start Date<TAB>End Date.

        Berikut adalah backlog baru yang harus Anda proses:
        --- BACKLOG BARU ---
        {raw_backlog_text}
        --- AKHIR BACKLOG BARU ---

        Sekarang, proses backlog di atas, tetapkan Epic sesuai aturan konsistensi, dan hasilkan output dalam format CSV.
        """
        return prompt

    # --- process_with_llm SEKARANG MENERIMA KONTEKS ---
    def process_with_llm(self, raw_backlog_text: str, existing_epics: list[str]) -> str:
        prompt = self._create_prompt(raw_backlog_text, existing_epics)
        # ... (sisa fungsi ini sama, hanya meneruskan prompt)
        print("Mengirim permintaan ke Google Gemini dengan konteks Epic...")
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

    # --- run_with_text SEKARANG MENERIMA KONTEKS ---
    def run_with_text(self, raw_text: str, existing_epics: list[str]) -> pd.DataFrame | None:
        llm_result = self.process_with_llm(raw_text, existing_epics)
        # ... (sisa fungsi ini sama, hanya memanggil process_with_llm dengan argumen baru)
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