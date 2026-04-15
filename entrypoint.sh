#!/bin/bash
set -e

echo "========================================"
echo "Running Django migrations..."
echo "========================================"
python manage.py migrate --noinput

echo "========================================"
echo "Collecting static files..."
echo "========================================"
python manage.py collectstatic --noinput

echo "========================================"
echo "Creating superuser if env vars exist..."
echo "========================================"
if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_EMAIL" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
    python manage.py createsuperuser --noinput || true
fi

echo "========================================"
echo "Starting command: $@"
echo "========================================"
exec "$@"
