#!/bin/sh
set -eu

echo "Applying Django migrations..."
python manage.py migrate --noinput

echo "Starting Domino backend..."
exec "$@"
