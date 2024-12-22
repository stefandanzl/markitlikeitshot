#!/bin/bash
set -e

echo "Starting services..."

# Ensure log directory exists
mkdir -p /app/logs

# Set permissions based on environment
if [ "$ENVIRONMENT" = "development" ] || [ "$ENVIRONMENT" = "test" ]; then
    # Development/Test: Allow host machine access
    sudo chown -R $(id -u):$(id -g) /app/logs
    sudo chmod 775 /app/logs
else
    # Production: Restrictive permissions
    sudo chown -R appuser:appuser /app/logs
    sudo chmod 755 /app/logs
fi

# Initialize logrotate state if it doesn't exist
if [ ! -f /var/lib/logrotate/status ]; then
    sudo touch /var/lib/logrotate/status
    sudo chmod 644 /var/lib/logrotate/status
fi

# Start the application
echo "Starting uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 "$@"