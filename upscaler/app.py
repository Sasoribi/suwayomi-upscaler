"""Flask application with Gunicorn entry point."""
import logging

from flask import Flask, Response, jsonify, request

from upscaler.cache import Cache
from upscaler.config import Config
from upscaler.convert import handle_convert
from upscaler.proxy import handle_proxy
from upscaler.worker import read_audit

logging.basicConfig(level=getattr(logging, Config.LOG_LEVEL),
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50MB max upload

cache = Cache()


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/cache/stats")
def stats():
    return jsonify(cache.stats())


@app.route("/audit")
def audit():
    limit = request.args.get("limit", 100, type=int)
    records = read_audit(limit)
    return jsonify(records)


@app.route("/convert", methods=["POST"])
def convert():
    return handle_convert()


@app.route("/api/v1/manga/<path:subpath>")
def proxy(subpath):
    return handle_proxy(subpath, request.query_string)


@app.errorhandler(413)
def too_large(_e):
    return Response("Image too large", status=413)


@app.errorhandler(Exception)
def handle_unexpected(e):
    logger.exception("Unhandled error")
    return Response("Internal error", status=500)
