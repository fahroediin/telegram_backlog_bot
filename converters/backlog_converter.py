# converters/backlog_converter.py
import pandas as pd
import google.generativeai as genai
import re
import io

def convert_mixed_language_date(date_str: str) -> str | None:
    if not isinstance(date_str, str) or not date_str.strip():
        return None
    month_map = {
        'januari': 'January', 'februari': 'February', 'maret': 'March',
        'april': 'April', 'mei': 'May', 'juni': 'June',
        'juli': 'July', 'agustus': 'August', 'september': 'September',
        'oktober': 'October', 'november': 'November', 'desember': 'December'
    }
    try:
        processed_str = date_str.lower()
        for id_month, en_month in month_map.items():
            processed_str = processed_str.replace(id_month, en_month)
        return processed_str
    except Exception:
        return date_str

class BacklogProcessor:
    def __init__(self, api_keys_string: str):
        if not api_keys_string:
            raise ValueError("String API Key tidak ditemukan.")
        # --- PERUBAHAN UTAMA: Tangani daftar key ---
        self.api_keys = [key.strip() for key in api_keys_string.split(',')]
        self.current_key_index = 0
        print(f"BacklogProcessor diinisialisasi dengan {len(self.api_keys)} API key.")

    def _rotate_and_configure_api_key(self):
        """Memilih key berikutnya dalam daftar dan mengonfigurasi API."""
        # Pindah ke key berikutnya
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        
        current_key = self.api_keys[self.current_key_index]
        print(f"Menggunakan API Key #{self.current_key_index + 1}...")
        genai.configure(api_key=current_key)

    def _create_prompt(self, raw_backlog_text: str, existing_epics: list[str]) -> str:
        epics_list_str = ", ".join(f'"{epic}"' for epic in existing_epics)
        prompt = f"""
        Anda adalah seorang Agile Project Manager yang sangat ahli dan konsisten.
        Tugas Anda adalah menganalisis backlog baru dan menetapkan Epic untuk setiap item.

        KONTEKS PENTING:
        Berikut adalah daftar Epic yang SUDAH ADA di dalam spreadsheet:
        [{epics_list_str}]

        ATURAN UTAMA:
        1.  **GUNAKAN KEMBALI EPIC YANG ADA**: Untuk setiap backlog, periksa apakah topiknya cocok dengan salah satu Epic yang sudah ada. Jika cocok, HARUS gunakan nama Epic yang persis sama.
        2.  **BUAT EPIC BARU JIKA PERLU**: Hanya jika sebuah backlog memiliki topik yang benar-benar baru, Anda boleh membuat nama Epic baru.
        3.  **Format Output**: Hasil akhir HARUS berupa teks CSV dengan pemisah pipa '|', tanpa teks pembuka/penutup.
        4.  **Kolom Output**: Urutan kolom harus: Epic|Backlog|PIC|Status|Start Date|End Date

        FORMAT INPUT:
        Setiap baris input dipisahkan oleh TAB: Backlog<TAB>Canonical Backlog<TAB>PIC<TAB>Status<TAB>Start Date<TAB>End Date.
        Gunakan kolom 'Backlog' untuk memahami konteks, abaikan 'Canonical Backlog'.

        Berikut adalah backlog baru yang harus Anda proses:
        --- BACKLOG BARU ---
        {raw_backlog_text}
        --- AKHIR BACKLOG BARU ---

        Sekarang, proses backlog di atas, tetapkan Epic, dan hasilkan output dalam format CSV.
        """
        return prompt

    def _call_llm(self, prompt: str) -> str:
        # --- PERUBAHAN UTAMA: Lakukan rotasi sebelum setiap panggilan ---
        self._rotate_and_configure_api_key()
        
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

    def _parse_llm_response_to_df(self, llm_response: str) -> pd.DataFrame:
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

    def get_epics_for_new_tasks(self, intermediate_df: pd.DataFrame, existing_epics: list[str]) -> pd.DataFrame | None:
        raw_text = intermediate_df.to_csv(sep='\t', index=False, header=True)
        prompt = self._create_prompt(raw_text, existing_epics)
        llm_result = self._call_llm(prompt)
        if not llm_result: return None
        
        structured_data = self._parse_llm_response_to_df(llm_result)
        if structured_data.empty: return None
        
        if len(structured_data) == len(intermediate_df):
            structured_data['Canonical Backlog'] = intermediate_df['Canonical Backlog'].values
        else:
            print("Peringatan: Jumlah baris dari LLM tidak cocok dengan input. 'Canonical Backlog' tidak dapat digabungkan kembali.")
            return None
        
        if 'Start Date' in structured_data.columns:
            structured_data['Start Date'] = structured_data['Start Date'].apply(convert_mixed_language_date)
        if 'End Date' in structured_data.columns:
            structured_data['End Date'] = structured_data['End Date'].apply(convert_mixed_language_date)
        
        return structured_data