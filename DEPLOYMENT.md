# Deployment Guide

This guide covers deployment options for the aws-simple library.

## PyPI Publishing

### Prerequisites

1. Create accounts:
   - PyPI: https://pypi.org/account/register/
   - Test PyPI: https://test.pypi.org/account/register/

2. Generate API tokens:
   - PyPI: https://pypi.org/manage/account/token/
   - Test PyPI: https://test.pypi.org/manage/account/token/

3. Add secrets to GitHub repository:
   - `PYPI_API_TOKEN` - Production PyPI token
   - `TEST_PYPI_API_TOKEN` - Test PyPI token

### Manual Publishing

#### Test PyPI

```bash
# Build package
python -m build

# Upload to Test PyPI
twine upload --repository testpypi dist/*

# Test installation
pip install --index-url https://test.pypi.org/simple/ aws-simple
```

#### Production PyPI

```bash
# Build package
python -m build

# Upload to PyPI
twine upload dist/*

# Verify installation
pip install aws-simple
```

### Automated Publishing (GitHub Actions)

#### Release Process

1. Update version in [pyproject.toml](pyproject.toml)
2. Commit and push changes
3. Create a new release on GitHub:
   ```bash
   git tag v0.1.0
   git push origin v0.1.0
   ```
4. Go to GitHub → Releases → Create new release
5. Choose the tag you just pushed
6. Write release notes
7. Publish release

The [publish workflow](.github/workflows/publish.yml) will automatically:
- Build the package
- Run tests
- Publish to PyPI

## Docker Deployment

### Building Docker Image

```bash
# Build image
docker build -t aws-simple:0.1.0 .

# Tag for registry
docker tag aws-simple:0.1.0 your-registry/aws-simple:0.1.0

# Push to registry
docker push your-registry/aws-simple:0.1.0
```

### Docker Compose

Create a `docker-compose.override.yml` for your environment:

```yaml
version: '3.8'

services:
  aws-simple:
    environment:
      - AWS_REGION=us-east-1
      - AWS_S3_BUCKET=my-production-bucket
      - AWS_BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
    # In production, use IAM roles instead of credentials
```

Run:
```bash
docker-compose up
```

## AWS Deployment

### Lambda Function

Create a Lambda layer with aws-simple:

```bash
# Create layer directory
mkdir -p layer/python

# Install package
pip install aws-simple -t layer/python/

# Create layer package
cd layer
zip -r aws-simple-layer.zip python/

# Upload to AWS Lambda Layers
aws lambda publish-layer-version \
    --layer-name aws-simple \
    --zip-file fileb://aws-simple-layer.zip \
    --compatible-runtimes python3.10 python3.11 python3.12
```

Example Lambda function:
```python
from aws_simple import s3, textract, bedrock

def lambda_handler(event, context):
    # Extract document from S3
    doc = textract.extract_text_from_s3(event['document_key'])

    # Analyze with Bedrock
    summary = bedrock.invoke(f"Summarize: {doc.full_text}")

    return {
        'statusCode': 200,
        'body': summary
    }
```

### ECS/Fargate

Use the Dockerfile to deploy on ECS:

1. Push Docker image to ECR:
```bash
# Authenticate with ECR
aws ecr get-login-password --region us-east-1 | \
    docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

# Tag and push
docker tag aws-simple:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/aws-simple:latest
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/aws-simple:latest
```

2. Create ECS task definition with environment variables
3. Use IAM task role for AWS credentials

### EC2

```bash
# SSH into EC2 instance
ssh ec2-user@your-instance

# Install package
pip install aws-simple

# Configure via IAM instance role (recommended)
# Or set environment variables
export AWS_REGION=us-east-1
export AWS_S3_BUCKET=my-bucket

# Run your application
python your_app.py
```

## Environment Configuration

### Production Best Practices

1. **Use IAM Roles** (never hardcode credentials):
   - Lambda: Lambda execution role
   - ECS/Fargate: Task role
   - EC2: Instance profile

2. **Environment Variables**:
   ```bash
   AWS_REGION=us-east-1
   AWS_S3_BUCKET=production-bucket
   AWS_BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
   ```

3. **Secrets Management**:
   - Use AWS Secrets Manager for sensitive data
   - Use AWS Systems Manager Parameter Store for config

### Multi-Environment Setup

Create environment-specific configuration:

```bash
# .env.development
AWS_REGION=us-east-1
AWS_S3_BUCKET=dev-bucket

# .env.staging
AWS_REGION=us-east-1
AWS_S3_BUCKET=staging-bucket

# .env.production
AWS_REGION=us-east-1
AWS_S3_BUCKET=production-bucket
```

Load appropriate config:
```python
from dotenv import load_dotenv
import os

env = os.getenv('ENVIRONMENT', 'development')
load_dotenv(f'.env.{env}')

from aws_simple import s3
```

## Monitoring and Logging

### CloudWatch

The library uses standard Python logging. Configure CloudWatch:

```python
import logging
import watchtower

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()
logger.addHandler(watchtower.CloudWatchLogHandler())

from aws_simple import s3

# Logs will go to CloudWatch
s3.upload_file("doc.pdf", "docs/doc.pdf")
```

### Error Tracking

Integrate with error tracking services:

```python
import sentry_sdk
from aws_simple import textract
from aws_simple.exceptions import TextractError

sentry_sdk.init(dsn="your-sentry-dsn")

try:
    doc = textract.extract_text_from_s3("document.pdf")
except TextractError as e:
    # Error automatically sent to Sentry
    raise
```

## Versioning Strategy

Follow Semantic Versioning (SemVer):

- **MAJOR** (1.0.0): Breaking API changes
- **MINOR** (0.1.0): New features, backward compatible
- **PATCH** (0.0.1): Bug fixes, backward compatible

Update version in:
1. [pyproject.toml](pyproject.toml)
2. [src/aws_simple/__init__.py](src/aws_simple/__init__.py)

## Rollback Procedures

### PyPI

If a bad version is published:

1. Yank the release (doesn't delete, but prevents new installs):
```bash
pip install pkginfo
python -c "from pkginfo import Wheel; print(Wheel('dist/aws_simple-0.1.0-py3-none-any.whl'))"
# Contact PyPI support to yank
```

2. Publish a fixed version with incremented patch number

### Docker

Roll back to previous image:
```bash
docker pull your-registry/aws-simple:0.0.9
docker tag your-registry/aws-simple:0.0.9 your-registry/aws-simple:latest
docker push your-registry/aws-simple:latest
```

### Lambda

Revert to previous layer version:
```bash
aws lambda update-function-configuration \
    --function-name your-function \
    --layers arn:aws:lambda:region:account:layer:aws-simple:previous-version
```

## Health Checks

Example health check endpoint:

```python
from aws_simple import s3
from aws_simple.exceptions import AWSSimpleError

def health_check():
    try:
        # Test S3 connectivity
        s3.list_objects(prefix="health/", max_keys=1)
        return {"status": "healthy", "aws_connectivity": "ok"}
    except AWSSimpleError as e:
        return {"status": "unhealthy", "error": str(e)}
```
