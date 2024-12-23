#!/bin/bash
set -e

echo "Starting services..."

# Ensure log directory exists with correct permissions
mkdir -p /app/logs
sudo chown -R appuser:appuser /app/logs
sudo chmod 755 /app/logs

# Start cron service
echo "Starting cron service..."
sudo service cron start

# Verify cron is running using service command
if ! sudo service cron status >/dev/null 2>&1; then
    echo "ERROR: Cron service failed to start"
    exit 1
fi
echo "Cron service started successfully"

# Start the application
echo "Starting uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 "$@"