"""
Naskah — backend penerjemah jurnal (FastAPI) + pembayaran Midtrans.

Alur: upload -> hitung harga (per halaman) -> checkout (Snap/QRIS) ->
konfirmasi pembayaran -> terjemah (pdf2zh + DeepSeek) -> unduh.

Jalankan dari root proyek:  .\run_web.ps1
"""
import os
import time
import uuid
import base64
import threading
from pathlib import Path
from string import Template

import requests
import fitz  # PyMuPDF
from fastapi import FastAPI, UploadFile, File, HTTPException, Body
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
for k, v in ENV.items():
    os.environ.setdefault(k, v)

PROMPT_TEMPLATE = Template(PROMPT_FILE.read_text(encoding="utf-8"))

# Midtrans
MID_SERVER = ENV.get("MIDTRANS_SERVER_KEY", "")
MID_CLIENT = ENV.get("MIDTRANS_CLIENT_KEY", "")
MID_PROD = ENV.get("MIDTRANS_PRODUCTION", "false").lower() == "true"
SNAP_URL = ("https://app.midtrans.com/snap/v1/transactions" if MID_PROD
            else "https://app.sandbox.midtrans.com/snap/v1/transactions")
STATUS_BASE = ("https://api.midtrans.com/v2" if MID_PROD
               else "https://api.sandbox.midtrans.com/v2")

# Harga
PRICE_PER_PAGE = int(ENV.get("PRICE_PER_PAGE", "500"))
PRICE_MIN = int(ENV.get("PRICE_MIN", "3000"))


def compute_price(pages: int) -> int:
    return max(pages * PRICE_PER_PAGE, PRICE_MIN)


def mid_headers():
    auth = base64.b64encode((MID_SERVER + ":").encode()).decode()
    return {"Authorization": "Basic " + auth, "Accept": "application/json",
            "Content-Type": "application/json"}


# muat model deteksi layout sekali
print("Memuat model deteksi layout…")
from pdf2zh.doclayout import OnnxModel  # noqa: E402

MODEL = OnnxModel.load_available()
print("Model siap. Pembayaran:", "AKTIF" if MID_SERVER else "BELUM dikonfigurasi")

uploads: dict[str, dict] = {}   # file_id -> {path, name, pages, price, order_id, paid, job_id}
jobs: dict[str, dict] = {}      # job_id  -> {status, progress, stage, mono, dual, error, name}


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
        pct = max(job["progress"], min(pct, 99))
        job["progress"] = pct
        job["stage"] = stage_for(pct)

    try:
        translate(files=[str(src)], output=str(jdir), lang_in="en", lang_out="id",
                  service="openai", thread=8, callback=cb, model=MODEL,
                  envs=ENV, prompt=PROMPT_TEMPLATE)
        mono = jdir / "source-mono.pdf"
        if not mono.exists():
            raise RuntimeError("Berkas hasil tidak ditemukan.")
        job.update({"progress": 100, "stage": "Menjilid naskah hasil…",
                    "status": "done", "mono": str(mono),
                    "dual": str(jdir / "source-dual.pdf")})
    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)[:300]


app = FastAPI(title="Naskah")


@app.get("/api/config")
async def get_config():
    return {"client_key": MID_CLIENT, "production": MID_PROD,
            "payment_enabled": bool(MID_SERVER and MID_CLIENT),
            "price_per_page": PRICE_PER_PAGE, "price_min": PRICE_MIN}


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(400, "Hanya berkas PDF yang didukung.")
    data = await file.read()
    if len(data) > 60 * 1024 * 1024:
        raise HTTPException(400, "Ukuran berkas melebihi 60 MB.")
    file_id = uuid.uuid4().hex[:12]
    jdir = JOBS_DIR / file_id
    jdir.mkdir(parents=True, exist_ok=True)
    src = jdir / "source.pdf"
    src.write_bytes(data)
    try:
        with fitz.open(str(src)) as d:
            pages = d.page_count
    except Exception:
        raise HTTPException(400, "PDF tidak dapat dibaca.")
    price = compute_price(pages)
    uploads[file_id] = {"path": str(src), "name": file.filename, "pages": pages,
                        "price": price, "order_id": None, "paid": False, "job_id": None}
    return {"file_id": file_id, "name": file.filename, "pages": pages, "price": price}


@app.post("/api/checkout")
async def checkout(payload: dict = Body(...)):
    if not MID_SERVER:
        raise HTTPException(503, "Pembayaran belum dikonfigurasi di server.")
    u = uploads.get(payload.get("file_id"))
    if not u:
        raise HTTPException(404, "Berkas tidak ditemukan. Unggah ulang.")
    order_id = f"naskah-{payload['file_id']}-{int(time.time())}"
    body = {
        "transaction_details": {"order_id": order_id, "gross_amount": u["price"]},
        "item_details": [{"id": "terjemahan", "price": u["price"], "quantity": 1,
                          "name": f"Terjemahan jurnal {u['pages']} halaman"}],
        "credit_card": {"secure": True},
    }
    r = requests.post(SNAP_URL, json=body, headers=mid_headers(), timeout=30)
    if r.status_code not in (200, 201):
        raise HTTPException(502, f"Midtrans menolak: {r.text[:160]}")
    u["order_id"] = order_id
    return {"order_id": order_id, "token": r.json()["token"], "gross_amount": u["price"]}


def midtrans_status(order_id: str) -> dict:
    r = requests.get(f"{STATUS_BASE}/{order_id}/status", headers=mid_headers(), timeout=30)
    return r.json() if r.status_code == 200 else {}


@app.post("/api/confirm")
async def confirm(payload: dict = Body(...)):
    file_id = payload.get("file_id")
    u = uploads.get(file_id)
    if not u:
        raise HTTPException(404, "Berkas tidak ditemukan.")
    if u.get("job_id"):
        return {"job_id": u["job_id"]}          # idempoten: sudah mulai
    order_id = payload.get("order_id") or u.get("order_id")
    st = midtrans_status(order_id)
    ts = st.get("transaction_status")
    fr = st.get("fraud_status", "accept")
    if ts in ("settlement", "capture") and fr in ("accept", None):
        u["paid"] = True
        job_id = uuid.uuid4().hex[:12]
        jdir = Path(u["path"]).parent
        jobs[job_id] = {"status": "queued", "progress": 0, "stage": "Menyiapkan naskah…",
                        "name": u["name"], "mono": None, "dual": None, "error": None}
        u["job_id"] = job_id
        threading.Thread(target=run_job, args=(job_id, Path(u["path"]), jdir),
                         daemon=True).start()
        return {"job_id": job_id}
    if ts in ("pending", None):
        raise HTTPException(402, "Pembayaran belum terkonfirmasi.")
    raise HTTPException(400, f"Pembayaran {ts}.")


@app.get("/api/status/{job_id}")
async def status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job tidak ditemukan.")
    return {"status": job["status"], "progress": job["progress"],
            "stage": job["stage"], "error": job["error"], "name": job["name"]}


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
    return FileResponse(path, media_type="application/pdf", filename=f"{base}-{suffix}.pdf")


app.mount("/", StaticFiles(directory=str(WEB), html=True), name="web")
