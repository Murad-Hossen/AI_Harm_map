.PHONY: install test lint check

install:
	pip install -e .
	pip install -r requirements-dev.txt

test:
	pytest

lint:
	ruff check src tests tools scripts

check: lint test
