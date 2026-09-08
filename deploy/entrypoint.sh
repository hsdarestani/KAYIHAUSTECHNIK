#!/bin/sh
set -eu
if [ "${POSTGRES_HOST:-}" ]; then
  echo "Waiting for PostgreSQL..."
  until nc -z "${POSTGRES_HOST}" "${POSTGRES_PORT:-5432}"; do sleep 1; done
fi
python manage.py collectstatic --noinput
exec "$@"
