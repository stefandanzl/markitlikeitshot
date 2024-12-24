#!/bin/bash
set -e

echo "Starting services..."

# After creating log directory
mkdir -p /app/logs
sudo chown -R appuser:appuser /app/logs
sudo chmod -R 755 /app/logs
touch /app/logs/app_development.log /app/logs/sql_development.log /app/logs/audit_development.log
sudo chown appuser:appuser /app/logs/*.log
sudo chmod 644 /app/logs/*.log

# Start cron service
echo "Starting cron service..."
sudo /usr/sbin/service cron start

# Verify cron is running using service command
if ! sudo /usr/sbin/service cron status >/dev/null 2>&1; then
    echo "ERROR: Cron service failed to start"
    exit 1
fi
echo "Cron service started successfully"

# Start the application
echo "Starting uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 "$@"