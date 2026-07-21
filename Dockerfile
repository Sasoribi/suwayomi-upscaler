FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libomp5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Engine binaries must be mounted or bundled separately
# See README for engine installation

ENV PORT=8765

EXPOSE 8765

CMD gunicorn upscaler.app:app \
    --bind 0.0.0.0:$PORT \
    --worker-class gevent \
    --workers 4 \
    --timeout 120
