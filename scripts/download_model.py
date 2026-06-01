"""Unduh model DocLayout-YOLO ONNX secara tahan-banting (streaming + multi-mirror)
lalu simpan di lokasi cache babeldoc agar pdf2zh tidak perlu mengunduh lagi.
"""
import hashlib
import sys
from pathlib import Path
import requests

SHA3 = "60be061226930524958b5465c8c04af3d7c03bcb0beb66454f5da9f792e3cf2a"
DEST = Path.home() / ".cache" / "babeldoc" / "models" / "doclayout_yolo_docstructbench_imgsz1024.onnx"

MIRRORS = [
    ("modelscope", "https://www.modelscope.cn/models/AI-ModelScope/DocLayout-YOLO-DocStructBench-onnx/resolve/master/doclayout_yolo_docstructbench_imgsz1024.onnx"),
    ("hf-mirror", "https://hf-mirror.com/wybxc/DocLayout-YOLO-DocStructBench-onnx/resolve/main/doclayout_yolo_docstructbench_imgsz1024.onnx?download=true"),
    ("huggingface", "https://huggingface.co/wybxc/DocLayout-YOLO-DocStructBench-onnx/resolve/main/doclayout_yolo_docstructbench_imgsz1024.onnx?download=true"),
]


def verify(path):
    if not path.exists():
        return False
    h = hashlib.sha3_256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest() == SHA3


if verify(DEST):
    print("Model sudah ada & valid:", DEST)
    sys.exit(0)

DEST.parent.mkdir(parents=True, exist_ok=True)
tmp = DEST.with_suffix(".onnx.part")

for name, url in MIRRORS:
    print(f"\n>>> Coba mirror: {name}")
    try:
        with requests.get(url, stream=True, timeout=(15, 60), allow_redirects=True) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            done = 0
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    if chunk:
                        f.write(chunk)
                        done += len(chunk)
                        if total:
                            pct = done * 100 // total
                            print(f"\r  {done//1024//1024} / {total//1024//1024} MB ({pct}%)", end="", flush=True)
            print()
        if verify(tmp):
            tmp.replace(DEST)
            print("BERHASIL & checksum cocok ->", DEST)
            sys.exit(0)
        else:
            print("Checksum TIDAK cocok, coba mirror lain...")
            tmp.unlink(missing_ok=True)
    except Exception as e:
        print(f"  Gagal di {name}: {type(e).__name__}: {str(e)[:150]}")
        tmp.unlink(missing_ok=True)

print("\nSemua mirror gagal.")
sys.exit(1)
