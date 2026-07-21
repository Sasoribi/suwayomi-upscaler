"""POST /convert handler — Suwayomi downloadConversion endpoint."""
import logging

from flask import Response, request

from upscaler.worker import Worker

logger = logging.getLogger(__name__)

worker = Worker()


def handle_convert() -> Response:
    if "image" not in request.files:
        return Response("Missing 'image' field", status=400)

    file = request.files["image"]
    image_data = file.read()

    if not image_data:
        return Response("Empty image", status=400)

    try:
        url = f"download:{file.filename or 'unknown'}"
        result = worker.process(url, image_data)
    except Exception as e:
        logger.exception("Convert failed, returning original")
        return Response(image_data, mimetype=file.content_type or "image/jpeg")

    return Response(result, mimetype="image/png")
