# Suwayomi Upscale Proxy

AI-powered manga image upscaling proxy for Suwayomi Server.

## Architecture

```
Browser → nginx → upscale-proxy (Flask+Gunicorn, :8765) → Suwayomi (:4567)
```

Two entry points:

- **GET `/api/v1/manga/{m}/{c}/page/{p}`** — reading (nginx transparent proxy)
- **POST `/convert`** — download (Suwayomi downloadConversion)

Zero changes required to Suwayomi or WebUI.

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Install an AI engine binary (pick one)
# Real-CUGAN (recommended):
#   https://github.com/nihui/realcugan-ncnn-vulkan/releases
# waifu2x:
#   https://github.com/nihui/waifu2x-ncnn-vulkan/releases
# Real-ESRGAN:
#   https://github.com/xinntao/Real-ESRGAN-ncnn-vulkan/releases

# 3. Run
make run

# Or with custom engine:
UPSCALE_ENGINE=waifu2x make run
```

## Engines

| Engine | CLI Binary | Quality | Speed (Iris Xe) |
|--------|-----------|---------|------------------|
| realcugan (default) | realcugan-ncnn-vulkan | Best for manga, no tile seams (-c 1) | ~8-12s/page |
| waifu2x | waifu2x-ncnn-vulkan | Good, may have tile seams | ~2-4s/page |
| realesrgan | realesrgan-ncnn-vulkan | Better | ~6-10s/page |

## Configuration

All via environment variables:

```bash
UPSCALE_ENGINE=realcugan     # realcugan | waifu2x | realesrgan
UPSCALE_SCALE=2              # 2 | 3 | 4
UPSCALE_THRESHOLD=2048       # skip images wider/taller than this (0 = never skip)
CACHE_MAX_GB=20              # disk cache limit
SUWAYOMI_URL=http://127.0.0.1:4567
PORT=8765
LOG_LEVEL=INFO
```

## Endpoints

| Path | Method | Description |
|------|--------|-------------|
| `/api/v1/manga/{m}/{c}/page/{p}` | GET | Proxy image from Suwayomi, upscale if needed |
| `/convert` | POST | Receive multipart image, return upscaled (for downloadConversion) |
| `/health` | GET | Health check |
| `/cache/stats` | GET | Cache statistics (file count, size) |

## Nginx Integration

See `nginx.conf.sample`. All `/api/v1/manga/` requests route through the proxy.
Everything else goes directly to Suwayomi.

## Suwayomi Download Integration

See `server.conf.sample`. Add to Suwayomi's `server.conf` to enable upscaling
during chapter download.

## Stability

- Engine failure → returns original image (graceful degradation)
- Suwayomi unreachable → returns 504
- GPU access is serialized (gevent Lock)
- Concurrent Suwayomi fetches capped at 20 (gevent BoundedSemaphore)
- Crash does not affect Suwayomi (independent process)

## License

MPL-2.0 — same as Suwayomi.
