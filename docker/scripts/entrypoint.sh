#!/bin/sh

# Wait for Redis to be ready
/app/docker/scripts/wait-for-it.sh redis:6379 --timeout=30 --strict -- echo "Redis is up!"

# Run migrations if needed (e.g., for Celery Beat's scheduler)
# python manage.py migrate # Uncomment if using Django/Flask-Migrate

# Execute the main command passed to the container
exec "$@"
