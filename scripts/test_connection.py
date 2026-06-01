"""Tes koneksi ke Sumopod/DeepSeek (OpenAI-compatible).
Mencoba base URL apa adanya, lalu fallback dengan /v1 kalau gagal.
"""
import os
from pathlib import Path
from openai import OpenAI

# load .env sederhana
env = {}
# .env ada di folder induk proyek (file ini di scripts/)
_env_path = Path(__file__).resolve().parent.parent / ".env"
for line in _env_path.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()

api_key = env["OPENAI_API_KEY"]
model = env["OPENAI_MODEL"]
base = env["OPENAI_BASE_URL"].rstrip("/")


def try_call(base_url):
    print(f"\n>>> Coba base_url = {base_url}  | model = {model}")
    client = OpenAI(api_key=api_key, base_url=base_url)
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user",
                   "content": "Terjemahkan ke Bahasa Indonesia, balas hanya hasilnya: 'The mitochondria is the powerhouse of the cell.'"}],
        temperature=0,
    )
    print("BERHASIL")
    print("Jawaban:", resp.choices[0].message.content.strip())


candidates = [base]
if not base.endswith("/v1"):
    candidates.append(base + "/v1")

for i, b in enumerate(candidates):
    try:
        try_call(b)
        print(f"\n=== Base URL yang BENAR: {b} ===")
        break
    except Exception as e:
        print(f"GAGAL ({type(e).__name__}): {str(e)[:200]}")
        if i == len(candidates) - 1:
            print("\nSemua kandidat gagal. Cek API key / nama model / base URL.")
