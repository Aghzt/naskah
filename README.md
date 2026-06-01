# Jurnal Translator (EN → ID)

Penerjemah PDF jurnal akademik dari Bahasa Inggris ke Bahasa Indonesia yang
**mempertahankan layout asli**: gambar, tabel, grafik, rumus, dan tata letak 2
kolom tetap utuh — hanya teksnya yang diterjemahkan (PDF in-place).

- **Engine:** [pdf2zh / PDFMathTranslate](https://github.com/PDFMathTranslate/PDFMathTranslate) + BabelDOC (lisensi AGPL-3.0)
- **Model AI:** DeepSeek (`deepseek-v4-pro`) via **Sumopod** (endpoint OpenAI-compatible)
- **Terjemahan akademik:** memakai prompt khusus (`prompts/prompt_akademik.txt`) —
  nama lembaga/proyek tetap Inggris, istilah serapan baku ("sekuensing"), format
  angka Indonesia, dan label struktural diterjemahkan.

## Struktur folder

```
jurnal-translator/
├── .env                 # rahasia: base URL Sumopod + API key + model (JANGAN di-commit)
├── .env.example         # template konfigurasi
├── requirements.txt     # daftar dependency
├── translate.ps1        # skrip 1-perintah untuk menerjemah
├── prompts/
│   └── prompt_akademik.txt   # prompt terjemahan akademik EN->ID
├── scripts/
│   ├── test_connection.py    # cek koneksi ke Sumopod/DeepSeek
│   └── download_model.py     # unduh manual model deteksi layout (jika auto gagal)
├── samples/             # PDF sumber untuk uji coba
├── output/              # hasil terjemahan (-mono.pdf & -dual.pdf)
└── .venv/               # virtual environment Python
```

## Setup (sekali saja)

```powershell
# 1. Buat virtual environment & install dependency
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 2. Siapkan konfigurasi
Copy-Item .env.example .env   # lalu isi OPENAI_API_KEY milikmu

# 3. Cek koneksi ke Sumopod/DeepSeek
.\.venv\Scripts\python.exe scripts\test_connection.py
```

> Catatan: saat pertama jalan, engine mengunduh model deteksi layout (~71 MB) dan
> font. Jika unduhan otomatis gagal (timeout ke HuggingFace), jalankan
> `.\.venv\Scripts\python.exe scripts\download_model.py` (memakai mirror ModelScope).

## Cara pakai

```powershell
# Terjemah seluruh PDF
.\translate.ps1 -Pdf "samples\namafile.pdf"

# Hanya halaman tertentu (hemat & cepat untuk uji coba)
.\translate.ps1 -Pdf "samples\namafile.pdf" -Pages "1-5"

# Lebih banyak request paralel (lebih cepat; hati-hati rate limit Sumopod)
.\translate.ps1 -Pdf "samples\namafile.pdf" -Thread 12
```

Hasil muncul di folder `output/`:
- `<nama>-mono.pdf` — full Bahasa Indonesia
- `<nama>-dual.pdf` — bilingual (halaman EN & ID selang-seling)

## Web app "Naskah" (frontend custom + backend)

Aplikasi web bertema **Bayt al-Ḥikmah** dengan animasi penyalin saat menerjemahkan.

```powershell
.\run_web.ps1
```

Lalu buka **http://localhost:8000**. Unggah PDF → animasi berjalan dengan progress
asli → unduh hasil. Backend (FastAPI, `backend/app.py`) menjalankan pdf2zh dengan
prompt akademik & DeepSeek; frontend ada di `web/index.html`.

Endpoint API: `POST /api/translate`, `GET /api/status/{id}`, `GET /api/download/{id}`.

> Alternatif cepat: web UI bawaan pdf2zh — `.\.venv\Scripts\pdf2zh.exe -i` (port 7860).

## Biaya

Sangat murah. Jurnal 50 halaman padat ≈ Rp 2.000 (harga DeepSeek resmi; Sumopod ada
markup — cek dashboard). Jurnal biasa 10–15 halaman ≈ Rp 500–800.

## Lisensi

Engine pdf2zh/BabelDOC berlisensi **AGPL-3.0**. Jika dijalankan sebagai layanan
web, source code (termasuk modifikasi) wajib disediakan ke pengguna sesuai AGPL.
