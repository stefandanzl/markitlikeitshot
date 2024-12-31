#!/bin/bash
set -e

echo "Starting services..."

# After creating log directory
echo "Creating log directories..."
mkdir -p /app/logs
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to create /app/logs directory"
    exit 1
fi

echo "Setting permissions for log directories..."
sudo chown -R appuser:appuser /app/logs
sudo chmod -R 755 /app/logs
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to set permissions for /app/logs"
    exit 1
fi

echo "Creating log files..."
touch /app/logs/app_development.log /app/logs/sql_development.log /app/logs/audit_development.log /app/logs/app_production.log /app/logs/sql_production.log /app/logs/audit_production.log
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to create log files"
    exit 1
fi

echo "Setting permissions for log files..."
sudo chown appuser:appuser /app/logs/*.log
sudo chmod 644 /app/logs/*.log
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to set permissions for log files"
    exit 1
fi

# Start cron service
echo "Starting cron service..."
sudo /usr/sbin/service cron start

# Verify cron is running using service command
if ! sudo /usr/sbin/service cron status >/dev/null 2>&1; then
    echo "ERROR: Cron service failed to start"
    exit 1
fi
echo "Cron service started successfully"

# Print directory structure and permissions for debugging
echo "Directory structure and permissions:"
ls -R /app/logs
echo "File permissions:"
ls -l /app/logs

# Start the application
echo "Starting uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 "$@"
