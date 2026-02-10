#!/bin/sh
set -e

echo "Running database migrations..."
django-admin migrate --noinput

echo "Starting application..."
exec "$@"
