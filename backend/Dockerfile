FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# collectstatic no necesita secretos ni base de datos; DEBUG=true evita exigir
# DJANGO_SECRET_KEY solo durante este paso de compilacion.
RUN DJANGO_DEBUG=true python manage.py collectstatic --noinput

# Usuario sin privilegios
RUN useradd --create-home --uid 10001 appuser && chown -R appuser /app
USER appuser

EXPOSE 8000

CMD ["sh", "-c", "gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 2 --timeout 120"]
