.PHONY: help install install-dev test test-cov lint format type-check build clean publish-test publish

help:
	@echo "Available commands:"
	@echo "  install       - Install package"
	@echo "  install-dev   - Install package with dev dependencies"
	@echo "  test          - Run tests"
	@echo "  test-cov      - Run tests with coverage report"
	@echo "  lint          - Run linter"
	@echo "  format        - Format code with ruff"
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
	pytest tests/ -v

test-cov:
	pytest tests/ -v --cov=aws_simple --cov-report=html --cov-report=term

lint:
	ruff check src/

format:
	ruff format src/ tests/

type-check:
	mypy src/

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
