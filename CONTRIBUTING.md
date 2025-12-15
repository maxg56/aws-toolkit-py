# Contributing to aws-simple

Thank you for your interest in contributing to aws-simple!

## Development Setup

### Prerequisites
- Python ≥ 3.10
- pip
- git

### Setup Development Environment

1. Clone the repository:
```bash
git clone https://github.com/yourusername/aws-toolkit-py.git
cd aws-toolkit-py
```

2. Create a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install development dependencies:
```bash
pip install -e ".[dev]"
```

4. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your AWS configuration
```

## Development Workflow

### Running Tests

Run all tests:
```bash
make test
# or
pytest tests/
```

Run tests with coverage:
```bash
make test-cov
# or
pytest tests/ --cov=aws_simple --cov-report=html
```

### Code Quality

Run linter:
```bash
make lint
# or
ruff check src/
```

Format code:
```bash
make format
# or
ruff format src/ tests/
```

Type checking:
```bash
make type-check
# or
mypy src/
```

### Building the Package

Build distribution files:
```bash
make build
# or
python -m build
```

Check package:
```bash
twine check dist/*
```

## CI/CD Pipeline

### Continuous Integration

The CI pipeline runs on every push and pull request:

1. **Tests** - Run on Python 3.10, 3.11, 3.12
2. **Linting** - Ruff checks code quality
3. **Type Checking** - mypy validates types
4. **Build** - Builds wheel and sdist packages

See [.github/workflows/ci.yml](.github/workflows/ci.yml)

### Publishing

#### Test PyPI (Manual)

Publish to Test PyPI for testing:
```bash
make publish-test
```

Or via GitHub Actions:
1. Go to Actions → Publish to PyPI
2. Run workflow → Select "testpypi"

#### PyPI (Automated)

Publishing to PyPI happens automatically on release:

1. Create a new release on GitHub
2. Tag format: `v0.1.0`
3. CI/CD automatically builds and publishes

See [.github/workflows/publish.yml](.github/workflows/publish.yml)

### Docker

Build Docker image:
```bash
docker build -t aws-simple:latest .
```

Run with docker-compose:
```bash
# Configure .env file first
docker-compose up
```

## Making Changes

### Branch Strategy

- `main` - Production-ready code
- `develop` - Development branch
- Feature branches: `feature/your-feature-name`
- Bug fixes: `fix/bug-description`

### Commit Messages

Follow conventional commits:
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `test:` - Test changes
- `refactor:` - Code refactoring
- `chore:` - Maintenance tasks

Example:
```
feat: add support for S3 presigned URLs
fix: handle empty Textract responses
docs: update installation instructions
```

### Pull Request Process

1. Create a feature branch
2. Make your changes
3. Add/update tests
4. Ensure all tests pass
5. Update documentation if needed
6. Submit pull request to `develop` branch

## Code Guidelines

### Python Style

- Follow PEP 8
- Use type hints
- Maximum line length: 100 characters
- Use ruff for formatting

### Testing

- Write tests for all new features
- Maintain >90% code coverage
- Use descriptive test names
- Mock external AWS calls

### Documentation

- Update README.md for user-facing changes
- Add docstrings to all public functions
- Include examples for new features

## Project Structure

```
aws-toolkit-py/
├── src/aws_simple/       # Source code
│   ├── __init__.py       # Public API
│   ├── config.py         # Configuration
│   ├── s3.py             # S3 module
│   ├── textract.py       # Textract module
│   ├── bedrock.py        # Bedrock module
│   ├── _clients.py       # Internal AWS clients
│   ├── exceptions.py     # Custom exceptions
│   ├── models/           # Data models
│   └── _parsers/         # Internal parsers
├── tests/                # Test suite
├── examples/             # Usage examples
├── .github/workflows/    # CI/CD workflows
└── docs/                 # Documentation
```

## Questions?

Open an issue on GitHub for questions or discussions.
