"""
Deploy Naskah ke Hugging Face Spaces (Docker).
Membuat Space, mengisi Secrets dari .env, lalu mengunggah kode.

Prasyarat: sudah `huggingface-cli login` (token Write).
Jalankan:  .\.venv\Scripts\python.exe scripts\deploy_hf.py
"""
from pathlib import Path
from huggingface_hub import HfApi, whoami

ROOT = Path(__file__).resolve().parent.parent
SPACE_NAME = "naskah"

api = HfApi()
me = whoami()                      # memakai token hasil login
user = me["name"]
repo_id = f"{user}/{SPACE_NAME}"
print(f"Login sebagai: {user}  ->  Space: {repo_id}")

# 1) buat Space (Docker)
api.create_repo(repo_id, repo_type="space", space_sdk="docker", exist_ok=True)
print("Space siap.")

# 2) set Secrets dari .env (nilai tidak dicetak)
env_path = ROOT / ".env"
keys = []
for line in env_path.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        k = k.strip()
        api.add_space_secret(repo_id=repo_id, key=k, value=v.strip())
        keys.append(k)
print("Secrets diisi:", ", ".join(keys))

# 3) unggah kode (besar/rahasia dikecualikan; PDF contoh otomatis LFS)
api.upload_folder(
    folder_path=str(ROOT),
    repo_id=repo_id,
    repo_type="space",
    ignore_patterns=[
        ".venv/**", "output/**", "samples/**", ".git/**",
        "**/__pycache__/**", "*.pyc", ".env",
    ],
)
print("\nSELESAI. Space sedang membangun image…")
print(f"URL: https://huggingface.co/spaces/{repo_id}")
print(f"App: https://{user}-{SPACE_NAME}.hf.space")
