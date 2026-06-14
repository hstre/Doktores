.PHONY: install test lint demo

install:
	python -m pip install -e ".[dev]"

test:
	python -m pytest

lint:
	python -m ruff check .

demo:
	python -m doktores "routing prefers locality but memory prefers recency under drift" \
		--topic routing --id C-12 --candidate "recency is a proxy for relevance, not its cause"
