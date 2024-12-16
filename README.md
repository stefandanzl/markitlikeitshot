# MarkItLikeItsHot - a FastAPI Wrapper for MarkItDown

A rough n ready FastAPI-based service that puts a simple API in front of [markitdown](https://github.com/microsoft/markitdown) by Microsoft. You can make requests to it to convert various file formats and web content to clean, formatted Markdown.

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

### Convert URL Content
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