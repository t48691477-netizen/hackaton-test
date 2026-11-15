FROM python:3.11-slim-bookworm

ARG PYTORCH_INDEX_URL=https://download.pytorch.org/whl/cpu

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    YOLO_OFFLINE=true \
    ULTRALYTICS_OFFLINE=true \
    YOLO_CONFIG_DIR=/tmp/Ultralytics \
    HF_HOME=/tmp/huggingface \
    TORCH_HOME=/tmp/torch

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home-dir /home/app --create-home app \
    && mkdir -p /app/data /app/weights /app/static/uploads /tmp/Ultralytics /tmp/huggingface /tmp/torch \
    && chown -R 10001:10001 /app/data /app/weights /app/static /tmp/Ultralytics /tmp/huggingface /tmp/torch

COPY requirements.txt ./requirements.txt
RUN python -m pip install --no-cache-dir --index-url "${PYTORCH_INDEX_URL}" torch torchvision \
    && python -m pip install --no-cache-dir -r requirements.txt

COPY --chown=10001:10001 app/ ./app/
COPY --chown=10001:10001 static/index.html ./static/index.html

USER 10001:10001
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
