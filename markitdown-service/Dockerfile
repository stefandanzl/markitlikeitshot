FROM python:3.13.1-slim

WORKDIR /app

# Accept UID/GID arguments with defaults
ARG UID=1000
ARG GID=1000

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    ffmpeg \
    libsm6 \
    libxext6 \
    libmagic1 \
    tesseract-ocr \
    python3-venv \
    curl \
    python3-ipython \
    cron \
    logrotate \
    sudo \
    && rm -rf /var/lib/apt/lists/*

# Create app user and group
RUN groupadd -g ${GID} appuser && \
    useradd -u ${UID} -g appuser -s /bin/bash -m appuser

# Configure sudo access for logrotate, directory management, and cron
RUN echo "appuser ALL=(root) NOPASSWD: /usr/sbin/logrotate, /bin/chown, /bin/chmod, /usr/sbin/cron, /usr/sbin/service cron *" > /etc/sudoers.d/appuser && \
    chmod 0440 /etc/sudoers.d/appuser

# Create necessary directories and set up log files
RUN mkdir -p /app/data /app/logs /var/lib/logrotate && \
    touch /var/lib/logrotate/status && \
    touch /app/logs/app_development.log && \
    touch /app/logs/sql_development.log && \
    touch /app/logs/audit_development.log && \
    touch /app/logs/app_production.log && \
    touch /app/logs/sql_production.log && \
    touch /app/logs/audit_production.log && \
    touch /app/logs/cli_development.log && \
    touch /app/logs/cli_production.log

# Set up permissions for logs and logrotate
RUN chmod 644 /var/lib/logrotate/status && \
    chown root:root /var/lib/logrotate/status && \
    chown -R appuser:appuser /app/logs && \
    chmod -R 755 /app/logs && \
    chmod 644 /app/logs/*.log

# Create and activate virtual environment
ENV VIRTUAL_ENV=/opt/venv
RUN python -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Copy requirements first for better caching
COPY requirements.txt .

# Update pip and install requirements in the virtual environment
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir wheel && \
    pip install --no-cache-dir -r requirements.txt && \
    find /opt/venv -name '*.pyc' -delete && \
    find /opt/venv -name '__pycache__' -delete

# Copy the application
COPY ./app /app/app
COPY manage.py /app/manage.py
COPY .coveragerc /app/.coveragerc

# Set coverage file permissions
RUN chown appuser:appuser /app/.coveragerc && \
    chmod 644 /app/.coveragerc

# Copy and set up configuration files
COPY docker/config/logrotate.conf /etc/logrotate.d/markitdown
COPY docker/config/log-maintenance /etc/cron.daily/log-maintenance
COPY docker/start.sh /app/start.sh

# Set proper permissions for files and directories
RUN chmod 755 /app/start.sh && \
    chmod 755 /etc/cron.daily/log-maintenance && \
    chmod 644 /etc/logrotate.d/markitdown && \
    chown root:root /etc/logrotate.d/markitdown && \
    chown root:root /etc/cron.daily/log-maintenance && \
    chown -R appuser:appuser /app/data && \
    chmod 755 /app/data

# Give appuser access to the virtual environment
RUN chown -R appuser:appuser $VIRTUAL_ENV

# Configure cron for root with proper environment
RUN echo 'SHELL=/bin/sh\n\
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin\n\
\n\
0 0 * * * root /usr/sbin/logrotate /etc/logrotate.d/markitdown\n\
' > /etc/cron.d/logrotate && \
    chmod 0644 /etc/cron.d/logrotate && \
    chown root:root /etc/cron.d/logrotate

# Set up cron log directory
RUN mkdir -p /var/log/cron && \
    chmod 755 /var/log/cron && \
    chown root:root /var/log/cron

# Create log directories with proper permissions
RUN mkdir -p /var/log/markitdown && \
    chown -R appuser:appuser /var/log/markitdown && \
    chmod -R 755 /var/log/markitdown

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Switch to appuser for running the application
USER appuser

# Use the startup script as the entry point
ENTRYPOINT ["/app/start.sh"]
