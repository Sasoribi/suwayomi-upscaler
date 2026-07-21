"""GET proxy handler — intercepts nginx-forwarded image requests for reading."""
import logging

import requests
from flask import Response, request

from upscaler.config import Config
from upscaler.worker import fetch_semaphore, Worker

logger = logging.getLogger(__name__)

LOOP_HEADER = "X-Suwayomi-Upscaler"

worker = Worker()


def handle_proxy(path: str, query_string: str) -> Response:
    # ▸ Guard: refuse if our own marker is already present.
    #   Happens when SUWAYOMI_URL points back through nginx instead of
    #   directly to Suwayomi's port (e.g., https://sasoribi.top).
    if request.headers.get(LOOP_HEADER):
        logger.critical(
            "Proxy loop detected! Request to %s came back to us. "
            "Check SUWAYOMI_URL — it must point directly to Suwayomi "
            "(e.g. http://192.168.1.143:4567), NOT through nginx.",
            path,
        )
        return Response(
            "Proxy loop detected — SUWAYOMI_URL must bypass nginx",
            status=508,
        )

    url = f"{Config.SUWAYOMI_URL}/api/v1/manga/{path}"
    if query_string:
        qs = query_string.decode() if isinstance(query_string, bytes) else query_string
        url += f"?{qs}"

    # ▸ Tag every outbound fetch so it can never loop back to us.
    fetch_headers = {LOOP_HEADER: "1"}

    # ▸ Thumbnails are tiny — grab and return directly, no GPU wasted.
    is_thumbnail = "thumbnail" in url

    with fetch_semaphore:
        try:
            resp = requests.get(url, headers=fetch_headers,
                                stream=True, timeout=Config.SUWAYOMI_TIMEOUT)
        except requests.RequestException as e:
            logger.error("Suwayomi unreachable: %s", e)
            return Response("Upstream unavailable", status=504)

    if resp.status_code != 200:
        return Response(resp.content, status=resp.status_code,
                        content_type=resp.headers.get("Content-Type", "image/jpeg"))

    if is_thumbnail:
        return Response(resp.content,
                        content_type=resp.headers.get("Content-Type", "image/jpeg"))

    try:
        result = worker.process(url, resp.content)
    except Exception as e:
        logger.exception("Unexpected error processing %s", url[:80])
        return Response(resp.content, content_type=resp.headers.get("Content-Type", "image/jpeg"))

    return Response(result, content_type="image/png",
                    headers={"Cache-Control": "max-age=604800"})
