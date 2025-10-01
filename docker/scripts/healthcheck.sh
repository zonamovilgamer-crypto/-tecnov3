#!/bin/sh
# healthcheck.sh

# This script checks the health of a Celery worker.
# It attempts to ping the worker and exits with 0 on success, 1 on failure.

# Ensure Celery app is correctly configured in core.celery_config
# Replace 'celery@%HOSTNAME%' with the actual worker name if not using default
celery -A core.celery_config inspect ping -d celery@$(hostname)

if [ $? -eq 0 ]; then
  echo "Celery worker is healthy."
  exit 0
else
  echo "Celery worker is unhealthy."
  exit 1
fi
