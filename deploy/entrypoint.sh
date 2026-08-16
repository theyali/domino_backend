#!/bin/sh
set -eu

echo "Applying Django migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Ensuring Django superuser exists..."
python manage.py shell <<'PY'
import os
from django.contrib.auth import get_user_model

User = get_user_model()
username = os.getenv("DJANGO_SUPERUSER_USERNAME", "admin")
password = os.getenv("DJANGO_SUPERUSER_PASSWORD", "admin")
email = os.getenv("DJANGO_SUPERUSER_EMAIL", "admin@localhost")

user, created = User.objects.get_or_create(
    username=username,
    defaults={"email": email},
)
user.email = email
user.is_staff = True
user.is_superuser = True
user.is_active = True
user.set_password(password)
user.save()

status = "created" if created else "updated"
print(f"Superuser '{username}' {status}.")
PY

echo "Starting Domino backend..."
exec "$@"
