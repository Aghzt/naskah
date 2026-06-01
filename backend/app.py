"""
Naskah — backend penerjemah jurnal (FastAPI).
Menyajikan web/ dan menjalankan pdf2zh (DeepSeek/Sumopod) dengan progress asli.

Jalankan dari root proyek:
    .\.venv\Scripts\python.exe -m uvicorn backend.app:app --port 8000
atau pakai run_web.ps1
"""
import os
import uuid
import threading
from pathlib import Path
from string import Template

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
JOBS_DIR = ROOT / "output" / "jobs"
PROMPT_FILE = ROOT / "prompts" / "prompt_akademik.txt"
JOBS_DIR.mkdir(parents=True, exist_ok=True)


# ---------- konfigurasi (.env) ----------
def load_env() -> dict:
    envs = {}
    env_path = ROOT / ".env"
    if not env_path.exists():
        raise RuntimeError(".env tidak ditemukan. Salin dari .env.example dan isi.")
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            envs[k.strip()] = v.strip()
    return envs


ENV = load_env()
# beberapa translator membaca dari os.environ juga
for k, v in ENV.items():
    os.environ.setdefault(k, v)

PROMPT_TEMPLATE = Template(PROMPT_FILE.read_text(encoding="utf-8"))

# muat model deteksi layout sekali (sudah ter-cache lokal)
print("Memuat model deteksi layout…")
from pdf2zh.doclayout import OnnxModel  # noqa: E402

MODEL = OnnxModel.load_available()
print("Model siap.")

jobs: dict[str, dict] = {}


def stage_for(pct: int) -> str:
    if pct < 8:
        return "Membuka gulungan naskah…"
    if pct < 30:
        return "Menelaah tata letak halaman…"
    if pct < 55:
        return "Menyalin kata demi kata…"
    if pct < 80:
        return "Mengalihbahasakan ke Indonesia…"
    if pct < 100:
        return "Menyelaraskan istilah ilmiah…"
    return "Menjilid naskah hasil…"


def run_job(job_id: str, src: Path, jdir: Path):
    from pdf2zh.high_level import translate

    job = jobs[job_id]
    job["status"] = "running"

    def cb(t):
        try:
            pct = int(t.n / t.total * 100) if getattr(t, "total", 0) else 0
        except Exception:
            pct = job["progress"]
        pct = max(job["progress"], min(pct, 99))  # monotonik, sisakan 100 utk akhir
        job["progress"] = pct
        job["stage"] = stage_for(pct)

    try:
        translate(
            files=[str(src)],
            output=str(jdir),
            lang_in="en",
            lang_out="id",
            service="openai",
            thread=8,
            callback=cb,
            model=MODEL,
            envs=ENV,
            prompt=PROMPT_TEMPLATE,
        )
        mono = jdir / "source-mono.pdf"
        if not mono.exists():
            raise RuntimeError("Berkas hasil tidak ditemukan.")
        job["progress"] = 100
        job["stage"] = "Menjilid naskah hasil…"
        job["status"] = "done"
        job["mono"] = str(mono)
        job["dual"] = str(jdir / "source-dual.pdf")
    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)[:300]


app = FastAPI(title="Naskah")


@app.post("/api/translate")
async def start_translate(file: UploadFile = File(...)):
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(400, "Hanya berkas PDF yang didukung.")
    data = await file.read()
    if len(data) > 60 * 1024 * 1024:
        raise HTTPException(400, "Ukuran berkas melebihi 60 MB.")
    job_id = uuid.uuid4().hex[:12]
    jdir = JOBS_DIR / job_id
    jdir.mkdir(parents=True, exist_ok=True)
    src = jdir / "source.pdf"
    src.write_bytes(data)
    jobs[job_id] = {
        "status": "queued", "progress": 0,
        "stage": "Menyiapkan naskah…", "name": file.filename,
        "mono": None, "dual": None, "error": None,
    }
    threading.Thread(target=run_job, args=(job_id, src, jdir), daemon=True).start()
    return {"job_id": job_id}


@app.get("/api/status/{job_id}")
async def status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job tidak ditemukan.")
    return {
        "status": job["status"], "progress": job["progress"],
        "stage": job["stage"], "error": job["error"], "name": job["name"],
    }


@app.get("/api/download/{job_id}")
async def download(job_id: str, kind: str = "mono"):
    job = jobs.get(job_id)
    if not job or job["status"] != "done":
        raise HTTPException(404, "Hasil belum siap.")
    path = job["mono"] if kind == "mono" else job["dual"]
    if not path or not Path(path).exists():
        raise HTTPException(404, "Berkas tidak ditemukan.")
    base = Path(job["name"]).stem
    suffix = "ID" if kind == "mono" else "ID-EN"
    return FileResponse(path, media_type="application/pdf",
                        filename=f"{base}-{suffix}.pdf")


# situs statis (paling akhir, agar /api tetap diprioritaskan)
app.mount("/", StaticFiles(directory=str(WEB), html=True), name="web")
