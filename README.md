# MarkItLikeItsHot - FastAPI Service for MarkItDown

[![Tests](https://github.com/matthewdeaves/markitlikeitshot/actions/workflows/tests.yml/badge.svg)](https://github.com/matthewdeaves/markitlikeitshot/actions/workflows/tests.yml)

A FastAPI service wrapping Microsoft's [markitdown](https://github.com/microsoft/markitdown) library. This service provides a robust API for converting various file formats and web content to clean, formatted Markdown with enterprise-grade features.

## Version

Current version: Refer to `settings.VERSION` in the code.

## API Documentation

- Swagger UI: Available at `/docs` (configurable via `settings.DOCS_URL`)
- ReDoc: Available at `/redoc` (configurable via `settings.REDOC_URL`)
- OpenAPI Schema: Available at `/openapi.json` (configurable via `settings.OPENAPI_URL`)

## Application Lifecycle

### Startup Process
On startup, the application:
1. Initializes logging
2. Sets up the log directory
3. Initializes the database
4. Checks log rotation configuration
5. Logs startup status and configuration details

### Shutdown Process
On shutdown, the application:
1. Flushes all logs
2. Logs the shutdown status

## Error Handling

The application includes:
- A global exception handler for unhandled exceptions
- A request validation error handler for invalid request parameters

## Audit Logging

The application logs the following audit events:
- Service startup
- Service shutdown
- Health checks

These logs include detailed information about the application state and configuration.

## Supported File Formats

The service supports various file formats for conversion. The exact list is defined in `settings.SUPPORTED_EXTENSIONS`.

## Dependencies

Key dependencies include:

- FastAPI
- Uvicorn
- SQLModel
- Pydantic
- Typer
- Rich
- Microsoft's MarkItDown library

For a complete list, refer to `requirements.txt` in the project root.

## This is Experimental

I have a software engineering background but I am not a Python expert. I've been using AI to help build features into MarkItLikeItsHot. While AI is helpful, it doesn't write great code. I've found adding tests that show exactly what I want helps get better results.... most of the time. Some of these tests were also written with AI help, so they need work too.

The early tests take a black box testing approach and call the API endpoints directly on the test container, which is slow. This made sense at the time (and I think still does) but it does make the tests run slowly.

Despite this I've got some solid features working:
- A command line tool for managing users and API keys
- The option to turn API key requirements on/off
- Adjustable rate limits
- A working conversion API
- Admin tools
- Different levels of logging across dev, test and production

## Features

### Core Functionality
- Convert multiple file formats to Markdown (PDF, DOCX, PPTX, HTML, etc.)
- Process direct text/HTML input
- Convert web pages with special Wikipedia handling
- Clean and standardize Markdown output

### Authentication Features
- API Key Authentication
- Rate Limiting
- Audit Logging
- Health Monitoring
- Comprehensive Error Handling
- CORS Support

### Management Features
- Interactive CLI for user and API key management
- Database initialization and maintenance tools
- System health checks and diagnostics
- Log rotation and cleanup

## Quick Start
On the first run of an environment the default admin API key will be generated and viewable in the logs.

### Development Environment
```bash
# Start development environment with hot reload
./run.sh dev
```

### Production Environment
```bash
# Start production environment
./run.sh prod
```

### Test Environment
To run the full test suite, use the following command:

```bash
# Run test suite
./run.sh -r test
```

This command is consistent with how you start other environments. The `-r` flag stands for "run". You can refer to the `run.sh` script for more details on how environments are started and managed.

The test suite includes various tests to ensure the functionality and reliability of the application. These tests cover different aspects such as API endpoints, database operations, and core functionalities.

To view the test logs, you can use:

```bash
# View test container logs
./run.sh -l test
```

If you need to clean up the test environment, use:

```bash
# Wipe test container
./run.sh -c test
```

Note: Running tests may take some time, especially if they include integration or end-to-end tests. Ensure you have a stable environment before running the test suite.

#### Rate Limiting Test

A separate script is provided to test the rate limiting functionality: `markitdown-service/tests/test_rate_limit.sh`. This script sends multiple requests to the API to verify that rate limiting is working correctly.

To use this script:

1. Open the script file and set your API key:
   ```bash
   API_KEY="YOUR-API-KEY-HERE"
   ```

2. Run the script:
   ```bash
   bash markitdown-service/tests/test_rate_limit.sh
   ```

The script will send 70 requests to the API with a short delay between each request. It will display the status of each request, including:
- HTTP status code
- Remaining rate limit
- Total rate limit
- Reset time for the rate limit

At the end, it will provide a summary of successful requests, rate-limited requests, and any errors encountered.

This test is useful for verifying that the rate limiting feature is functioning as expected and for fine-tuning rate limit settings.

### Viewing the Logs
On the first run of the development and production environments this will also show you the default admin API key generated on first run for the admin user. Subsequent restarts will not generate a new default API key, so make a note of it as these are not shown again.

```bash
# View production container logs
./run.sh -l prod

# View development container logs
./run.sh -l dev

# View test container logs
./run.sh -l test
```

### Destroying Environments
```bash
# -C (big C) to wipe all environments
./run.sh -C

# Wipe development container
./run.sh -c dev

# Wipe production container
./run.sh -c prod

# Wipe test container
./run.sh -c test
```

### The CLI
You can use the administration CLI on the development and production environments to manage users and api keys.

```bash
# Use the CLI on production
./run.sh -i prod

# Use the CLI on development
./run.sh -i dev
```

## API Endpoints

### Authentication
All endpoints require an API key (when enabled):
```bash
-H "X-API-Key: your-api-key"
```

### Convert File
```bash
curl -X POST "http://localhost:8000/api/v1/convert/file" \
     -H "X-API-Key: your-api-key" \
     -H "Content-Type: multipart/form-data" \
     -F "file=@path/to/document.docx"
```

### Convert HTML Text
```bash
curl -X POST "http://localhost:8000/api/v1/convert/text" \
     -H "X-API-Key: your-api-key" \
     -H "Content-Type: application/json" \
     -d '{"content": "<h1>Hello World</h1><p>This is a test</p>"}'
```

### Convert URL
```bash
curl -X POST "http://localhost:8000/api/v1/convert/url" \
     -H "X-API-Key: your-api-key" \
     -H "Content-Type: application/json" \
     -d '{"url": "https://example.com"}'
```

### Health Check
```bash
curl -X GET "http://localhost:8000/health"
```

The health check endpoint provides detailed information about the system status, including:
- Overall health status
- Application version
- Current environment
- Authentication status
- Supported file formats
- Database connection status
- Logging status
- Rate limiting configuration
- API key authentication settings

## Security Configuration

### API Key Authentication

#### Disabling API Key Authentication
API key authentication can be disabled for development or testing purposes:

1. Environment Variable Method:
```bash
export API_KEY_AUTH_ENABLED=false
./run.sh dev
```

2. Docker Compose Method:
Add to your service in docker-compose.yml:
```yaml
environment:
  - API_KEY_AUTH_ENABLED=false
```

3. .env File Method:
Create or modify .env in the project root:
```
API_KEY_AUTH_ENABLED=false
```

### Rate Limiting

Rate limiting is applied to all requests, regardless of whether API key authentication is enabled or disabled. The rate limiting is based on either the API key (if present) or the client's IP address. To modify the rate limiting settings:

```yaml
environment:
  - RATE_LIMIT_REQUESTS=100
  - RATE_LIMIT_PERIOD=minute
```

These settings define the number of requests allowed per time period for each unique API key or IP address. You can adjust these values to suit your needs.

### CORS Configuration

When API key authentication is disabled, you may want to restrict CORS:

```yaml
environment:
  - ALLOWED_ORIGINS=["http://localhost:3000"]
  - ALLOWED_METHODS=["GET", "POST"]
  - ALLOWED_HEADERS=["*"]
```

### Audit Logging

Audit logging tracks all API operations regardless of authentication status:

```yaml
environment:
  - AUDIT_LOG_ENABLED=true
  - AUDIT_LOG_RETENTION_DAYS=90
```

### Example Development Configuration

Complete example for local development:

```yaml
services:
  markitdown-dev:
    environment:
      - ENVIRONMENT=development
      - API_KEY_AUTH_ENABLED=false
      - LOG_LEVEL=DEBUG
      - RATE_LIMIT_REQUESTS=1000
      - RATE_LIMIT_PERIOD=hour
      - ALLOWED_ORIGINS=["*"]
      - AUDIT_LOG_ENABLED=true
      - DATABASE_URL=sqlite:///./data/dev_api_keys.db
```

### Verifying Configuration

Check current security settings:

```bash
# Using the CLI
./run.sh -i dev
# Select "Show Version Info" from the menu

# Or using curl
curl http://localhost:8000/health
```

The health endpoint response includes authentication status:

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "environment": "development",
  "auth_enabled": false,
  "database": "connected",
  "rate_limit": {
    "requests": 1000,
    "period": "hour"
  }
}
```

## Management CLI

### Interactive Mode
The easiest way to access the interactive CLI is:
```bash
# Launch interactive CLI for development environment
./run.sh -i dev

# Or for production
./run.sh -i prod
```

### Alternative Method (Direct Docker Access)
If needed, you can still access the CLI directly via Docker:
```bash
sudo docker exec -it markitlikeitshot-markitdown-dev-1 python manage.py interactive
```

### User Management
```bash
# Create new user
python manage.py users create --name "John Doe" --email "john@example.com"

# List users
python manage.py users list

# View user details
python manage.py users info 1
```

### API Key Management
```bash
# Create API key
python manage.py apikeys create --name "Test Key" --user-id 1

# List API keys
python manage.py apikeys list

# Deactivate API key
python manage.py apikeys deactivate 1
```

### System Management
```bash
# Initialize database
python manage.py init

# Check system health
python manage.py check

# Clean old logs
python manage.py clean
```

## Configuration

### Environment Variables
- `ENVIRONMENT`: development/production/test
- `API_KEY_AUTH_ENABLED`: Enable/disable API key authentication
- `LOG_LEVEL`: DEBUG/INFO/WARNING/ERROR/CRITICAL
- `RATE_LIMIT_REQUESTS`: Number of requests allowed per period
- `RATE_LIMIT_PERIOD`: Time period for rate limiting
- `LOG_DIR`: Directory for storing log files
- `ALLOWED_ORIGINS`: List of allowed origins for CORS
- `ALLOWED_METHODS`: List of allowed HTTP methods for CORS
- `ALLOWED_HEADERS`: List of allowed headers for CORS
- `API_KEY_HEADER_NAME`: Name of the header used for API key authentication

The application uses Pydantic's BaseSettings for managing these environment variables. Refer to `app/core/config/settings.py` for a complete list of configurable settings.

### Logging

The application uses a logging system with different loggers for various components:
- Main application logger
- API logger
- Database logger
- Security logger

Logs are stored in the directory specified by `LOG_DIR`. Log rotation is configured for production and development environments.

### Supported File Types
- Documents: .pdf, .docx, .pptx, .xlsx
- Audio: .wav, .mp3
- Images: .jpg, .jpeg, .png
- Web: .html, .htm
- Data: .txt, .csv, .json, .xml

## Project Structure
```
/markitlikeitshot
├── ai_dump.md
├── ai_dump.sh
├── docker-compose.yml
├── LICENSE
├── markitdown-service
│   ├── app
│   │   ├── api
│   │   │   └── v1
│   │   │       └── endpoints
│   │   │           ├── admin.py
│   │   │           └── conversion.py
│   │   ├── cli
│   │   │   ├── commands
│   │   │   │   ├── api_key.py
│   │   │   │   ├── logs.py
│   │   │   │   └── user.py
│   │   │   ├── interactive.py
│   │   │   ├── manage.py
│   │   │   └── utils
│   │   │       └── menu_utils.py
│   │   ├── core
│   │   │   ├── audit
│   │   │   │   ├── actions.py
│   │   │   │   ├── audit.py
│   │   │   │   └── __init__.py
│   │   │   ├── config
│   │   │   │   ├── __init__.py
│   │   │   │   └── settings.py
│   │   │   ├── errors
│   │   │   │   ├── base.py
│   │   │   │   ├── exceptions.py
│   │   │   │   ├── handlers.py
│   │   │   │   └── __init__.py
│   │   │   ├── __init__.py
│   │   │   ├── logging
│   │   │   │   ├── config.py
│   │   │   │   ├── formatters.py
│   │   │   │   ├── __init__.py
│   │   │   │   └── management.py
│   │   │   ├── rate_limiting
│   │   │   │   ├── limiter.py
│   │   │   │   └── middleware.py
│   │   │   ├── security
│   │   │   │   ├── api_key.py
│   │   │   │   └── user.py
│   │   │   └── validation
│   │   │       ├── __init__.py
│   │   │       └── validators.py
│   │   ├── db
│   │   │   ├── init_db.py
│   │   │   ├── __init__.py
│   │   │   └── session.py
│   │   ├── main.py
│   │   └── models
│   │       ├── auth
│   │       │   ├── api_key.py
│   │       │   └── user.py
│   │       └── __init__.py
│   ├── docker
│   │   ├── config
│   │   │   ├── log-maintenance
│   │   │   └── logrotate.conf
│   │   └── start.sh
│   ├── Dockerfile
│   ├── logs
│   │   ├── app_development.log
│   │   ├── audit_development.log
│   │   ├── audit_test.log
│   │   ├── audit_test.log.2024-12-27
│   │   ├── audit_test.log.2024-12-28
│   │   ├── cli_development.log
│   │   └── sql_development.log
│   ├── manage.py
│   ├── pytest.ini
│   ├── requirements.txt
│   └── tests
│       ├── api
│       ├── conftest.py
│       └── fixtures
├── README.md
└── run.sh
```

## Python Version

This project requires Python 3.8 or higher. You can check your Python version by running:

```bash
python --version
```

## Contributing

Contributions to MarkItLikeItsHot are welcome! Please follow these steps to contribute:

1. Fork the repository
2. Create a new branch for your feature or bug fix
3. Make your changes and commit them with a clear commit message
4. Push your changes to your fork
5. Create a pull request to the main repository

Please ensure your code adheres to the project's coding standards and includes appropriate tests.

## Troubleshooting

Here are some common issues and their solutions:

1. **API Key Authentication Issues**
   - Ensure the API key is correctly set in the request header
   - Check if API key authentication is enabled in the configuration

2. **Rate Limiting Errors**
   - Check the current rate limit settings in the configuration
   - If you're hitting limits too quickly, consider adjusting the settings or optimizing your requests

3. **File Conversion Errors**
   - Ensure the file format is supported (check the list of supported file types)
   - Verify the file is not corrupted or empty

4. **Database Connection Issues**
   - Check if the database URL is correctly set in the configuration
   - Ensure the database server is running and accessible

For more specific issues, please check the application logs or create an issue on the project's GitHub repository.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
