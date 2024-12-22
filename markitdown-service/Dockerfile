FROM python:3.13.1-slim

WORKDIR /app

# Accept UID/GID arguments with defaults
ARG UID=1000
ARG GID=1000

# Install system dependencies
RUN apt-get update && apt-get install -y \
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

# Configure sudo access for logrotate and directory management
RUN echo "appuser ALL=(root) NOPASSWD: /usr/sbin/logrotate, /bin/chown, /bin/chmod" > /etc/sudoers.d/appuser && \
    chmod 0440 /etc/sudoers.d/appuser

# Create necessary directories
RUN mkdir -p /app/data /app/logs /var/lib/logrotate && \
    touch /var/lib/logrotate/status

# Set up logrotate permissions
RUN chmod 644 /var/lib/logrotate/status && \
    chown root:root /var/lib/logrotate/status

# Create and activate virtual environment
ENV VIRTUAL_ENV=/opt/venv
RUN python -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Copy requirements first for better caching
COPY requirements.txt .

# Update pip and install requirements in the virtual environment
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the application
COPY ./app /app/app
COPY manage.py /app/manage.py

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
    chown -R appuser:appuser /app/logs /app/data && \
    chmod 755 /app/logs && \
    chmod 755 /app/data

# Give appuser access to the virtual environment
RUN chown -R appuser:appuser $VIRTUAL_ENV

# Configure cron for root
RUN echo "0 0 * * * /usr/sbin/logrotate /etc/logrotate.d/markitdown" > /etc/cron.d/logrotate && \
    chmod 0644 /etc/cron.d/logrotate

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Switch to appuser for running the application
USER appuser

# Use the startup script as the entry point
ENTRYPOINT ["/app/start.sh"]