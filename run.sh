#!/bin/bash
# Suwayomi Upscaler — realcugan on M4 GPU
# Ctrl+C to stop, auto-fallback on nginx side
DIR="$(cd "$(dirname "$0")" && pwd)"
export PATH="$DIR/waifu2x:$PATH"
export REALCUGAN_MODEL_PATH="$DIR/waifu2x/models-pro"
export WAIFU2X_MODEL_PATH="$DIR/waifu2x/models-upconv_7_anime_style_art_rgb"
export UPSCALE_ENGINE="${UPSCALE_ENGINE:-realcugan}"
export UPSCALE_SCALE="${UPSCALE_SCALE:-2}"
export UPSCALE_THRESHOLD="${UPSCALE_THRESHOLD:-1400}"
export CACHE_MAX_GB="${CACHE_MAX_GB:-10}"
export CACHE_DIR="${CACHE_DIR:-$DIR/cache}"
export LOG_DIR="${LOG_DIR:-$DIR/logs}"
export SUWAYOMI_URL="${SUWAYOMI_URL:-http://192.168.1.143:4567}"
export SUWAYOMI_TIMEOUT="${SUWAYOMI_TIMEOUT:-30}"
export FETCH_CONCURRENCY="${FETCH_CONCURRENCY:-20}"
export PORT="${PORT:-8765}"
export LOG_LEVEL="${LOG_LEVEL:-INFO}"

mkdir -p "$CACHE_DIR" "$LOG_DIR"

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║   Suwayomi Upscaler — realcugan (M4 GPU)    ║"
echo "╠══════════════════════════════════════════════╣"
echo "║  Port:     $PORT"
echo "║  Engine:   $UPSCALE_ENGINE (models-pro, ${UPSCALE_SCALE}x)"
echo "║  Threshold: ${UPSCALE_THRESHOLD}px max"
echo "║  Cache:    ${CACHE_MAX_GB}GB → $CACHE_DIR"
echo "║  Logs:     $LOG_DIR"
echo "║  Upstream: $SUWAYOMI_URL"
echo "║  Ctrl+C to stop"
echo "╚══════════════════════════════════════════════╝"
echo ""

exec "$DIR/venv/bin/gunicorn" upscaler.app:app \
    --bind "0.0.0.0:$PORT" \
    --worker-class gevent \
    --workers 2 \
    --timeout 180 \
    --chdir "$DIR" \
    --access-logfile "$LOG_DIR/access.log" \
    --error-logfile "$LOG_DIR/error.log" \
    --log-level "$LOG_LEVEL"
