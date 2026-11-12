#!/bin/sh
# Arranque del backend en produccion. Pasos opcionales controlados por variables,
# para plataformas sin "pre-deploy command" (p. ej. Render, plan gratuito).
#   RUN_MIGRATIONS=true      aplica migraciones antes de servir
#   IMPORT_SAMPLE_DATA=true  importa los CSV inventados de /app/sample-data
set -e

if [ "${RUN_MIGRATIONS:-false}" = "true" ]; then
    echo "[entrypoint] migrate"
    python manage.py migrate --noinput
fi

if [ "${IMPORT_SAMPLE_DATA:-false}" = "true" ]; then
    echo "[entrypoint] importando datos de ejemplo"
    python manage.py import_staffing_csvs \
        --staff-csv /app/sample-data/Staff.csv \
        --assignments-csv /app/sample-data/Assignments.csv \
        --replace || echo "[entrypoint] IMPORTACION FALLIDA: se conservan los datos anteriores"
fi

exec gunicorn config.wsgi:application \
    --bind "0.0.0.0:${PORT:-8000}" --workers 2 --timeout 120
