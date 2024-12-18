# MarkItLikeItsHot - a FastAPI Wrapper for MarkItDown

[![Tests](https://github.com/matthewdeaves/markitlikeitshot/actions/workflows/tests.yml/badge.svg)](https://github.com/matthewdeaves/markitlikeitshot/actions/workflows/tests.yml)

A rough n ready [FastAPI-based](https://fastapi.tiangolo.com/) service that puts a simple API in front of [markitdown](https://github.com/microsoft/markitdown) by Microsoft. You can make requests to it to convert various file formats and web content to clean, formatted Markdown.

## Features

Provides 3 API endpoints and:
- Supports file uploads, direct text input, and URLs
- Converts multiple file formats (PDF, DOCX, PPTX, HTML, etc.) to Markdown
- Fetches and converts web pages, with special handling for Wikipedia
- Cleans HTML content before conversion
- Formats and standardizes Markdown output

## Quick Start

```bash
# Build and run with Docker
docker compose build
docker compose up -d
```

## API Endpoints

### Convert File
```bash
curl -X POST "http://localhost:8000/convert/file" \
     -H "Content-Type: multipart/form-data" \
     -F "file=@path/to/document.docx"
```

### Convert HTML Text
```bash
curl -X POST "http://localhost:8000/convert/text" \
     -H "Content-Type: application/json" \
     -d '{"content": "<h1>Hello World</h1><p>This is a test</p>"}'
```

### Convert Wikipedia Content
```bash
curl -X POST "http://localhost:8000/convert/url" \
     -H "Content-Type: application/json" \
     -d '{"url": "https://en.wikipedia.org/wiki/Goat"}'
```

### For non-Wikipedia page
```bash
curl -X POST "http://localhost:8000/convert/url" \
     -H "Content-Type: application/json" \
     -d '{"url": "https://www.bbc.co.uk/news/articles/c6p229ldn4vo"}'
```

### Service Healthcheck
```bash
curl -X GET "http://localhost:8000/health"
```

## Testing

### Running Tests
To run the test suite:
```bash
# Run normal tests
sudo docker-compose --profile test run --rm test

# Run tests with debug logging
sudo docker-compose --profile test run --rm test /app/tests/test_api.py -v --capture=no --log-cli-level=DEBUG

# Run specific test
sudo docker-compose --profile test run --rm test /app/tests/test_api.py::test_convert_text_basic
```

### Test Configuration
Tests are configured via:
- `pytest.ini`: Controls test discovery and logging
- `conftest.py`: Provides test fixtures and configuration
- `test_api.py`: Contains the actual test cases

### Environment Variables
The test environment:
- Uses WARNING level logging by default
- Automatically removes test containers after completion
- Runs all tests in the `/tests` directory
- Includes rate limiting, file conversion, and API endpoint tests

## Project Structure

```
markitlikeitshot/
├── docker-compose.yml
├── markitdown-service
│   ├── app
│   │   ├── api
│   │   │   └── __init__.py
│   │   ├── core
│   │   │   ├── config.py
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── models
│   │   │   └── __init__.py
│   ├── Dockerfile
│   ├── pytest.ini
│   ├── requirements.txt
│   ├── test_files
│   │   └── TestDoc.docx
│   └── tests
│       ├── conftest.py
│       ├── __init__.py
│       └── test_api.py
└── README.md
```