# Naskah — Hugging Face Space (Docker)
FROM python:3.11-slim

# dependensi sistem untuk opencv / onnxruntime / pymupdf
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# user non-root (praktik baik HF Spaces)
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8

WORKDIR /home/user/app

# install dependency Python lebih dulu (cache layer)
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# salin kode aplikasi
COPY --chown=user . .

# pra-unduh model deteksi layout agar startup cepat (boleh gagal -> diulang saat runtime)
RUN python -c "from babeldoc.assets.assets import get_doclayout_onnx_model_path as g; print('model:', g())" || true

EXPOSE 7860
CMD ["python", "-m", "uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "7860"]
