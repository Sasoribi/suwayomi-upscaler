"""GET proxy handler — intercepts nginx-forwarded image requests for reading."""
import logging

import requests
from flask import Response

from upscaler.config import Config
from upscaler.worker import fetch_semaphore, Worker

logger = logging.getLogger(__name__)

worker = Worker()


def handle_proxy(path: str, query_string: str) -> Response:
    url = f"{Config.SUWAYOMI_URL}/api/v1/manga/{path}"
    if query_string:
        qs = query_string.decode() if isinstance(query_string, bytes) else query_string
        url += f"?{qs}"

    with fetch_semaphore:
        try:
            resp = requests.get(url, stream=True, timeout=Config.SUWAYOMI_TIMEOUT)
        except requests.RequestException as e:
            logger.error("Suwayomi unreachable: %s", e)
            return Response("Upstream unavailable", status=504)

    if resp.status_code != 200:
        return Response(resp.content, status=resp.status_code,
                        content_type=resp.headers.get("Content-Type", "image/jpeg"))

    try:
        result = worker.process(url, resp.content)
    except Exception as e:
        logger.exception("Unexpected error processing %s", url[:80])
        return Response(resp.content, content_type=resp.headers.get("Content-Type", "image/jpeg"))

    return Response(result, content_type="image/png",
                    headers={"Cache-Control": "max-age=604800"})
