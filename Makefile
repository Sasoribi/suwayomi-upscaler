.PHONY: run dev test clean

run:
	gunicorn upscaler.app:app \
		--bind 0.0.0.0:$(or $(PORT),8765) \
		--worker-class gevent \
		--workers 4 \
		--timeout 120 \
		--log-level $(or $(LOG_LEVEL),info)

dev:
	FLASK_APP=upscaler/app.py flask run --port $(or $(PORT),8765) --debug

test:
	python -m pytest tests/ -v

clean:
	rm -rf cache/ __pycache__/ upscaler/__pycache__/ upscaler/engines/__pycache__/
