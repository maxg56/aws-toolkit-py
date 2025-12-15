.PHONY: help install install-dev test test-cov lint format format-check type-check build clean publish-test publish

help:
	@echo "Available commands:"
	@echo "  install       - Install package"
	@echo "  install-dev   - Install package with dev dependencies"
	@echo "  test          - Run tests"
	@echo "  test-cov      - Run tests with coverage report"
	@echo "  lint          - Run linter (ruff)"
	@echo "  format        - Format code with black"
	@echo "  format-check  - Check code formatting without modifying"
	@echo "  type-check    - Run type checker"
	@echo "  build         - Build package"
	@echo "  clean         - Clean build artifacts"
	@echo "  publish-test  - Publish to Test PyPI"
	@echo "  publish       - Publish to PyPI"

install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"

test:
	python3 -m pytest tests/ -v

test-cov:
	python3 -m pytest tests/ -v --cov=aws_simple --cov-report=html --cov-report=term

lint:
	python3 -m ruff check src/

format:
	python3 -m black src/ tests/
	python3 -m ruff check --fix src/

format-check:
	python3 -m black --check src/ tests/
	python3 -m ruff check src/

type-check:
	python3 -m mypy src/

build: clean
	python -m build
	twine check dist/*

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

publish-test: build
	twine upload --repository testpypi dist/*

publish: build
	twine upload dist/*
