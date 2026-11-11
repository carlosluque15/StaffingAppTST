# Variables de entorno y secretos

Referencia de todas las variables que lee la aplicación (`backend/config/settings.py`,
`frontend/src/App.jsx`, `compose*.yaml`) y dónde se define cada una en cada entorno.

**Regla:** los valores secretos nunca van al repositorio, a una imagen Docker ni a un
archivo versionado. En local, en `.env` (ya ignorado por Git). En la nube, en el
gestor de secretos de la plataforma.

## Backend (Django)

| Variable | Obligatoria | Secreta | Valor local (`compose.yaml`) | Valor en producción |
|---|---|---|---|---|
| `DJANGO_DEBUG` | no (defecto `true`) | no | `true` | `false` — **siempre** |
| `DJANGO_SECRET_KEY` | sí si `DEBUG=false` | **sí** | vacía (se genera una aleatoria en cada arranque) | clave larga aleatoria, distinta por entorno |
| `DJANGO_ALLOWED_HOSTS` | sí en prod | no | `localhost,127.0.0.1` | solo el dominio del backend, p. ej. `api-xxxx.onrender.com` (sin `https://`) |
| `CORS_ALLOWED_ORIGINS` | sí en prod | no | `http://localhost:5173` | URL completa del frontend, con `https://` y sin `/` final |
| `CSRF_TRUSTED_ORIGINS` | sí en prod (para `/admin/`) | no | vacía | URL completa del backend, con `https://` |
| `DB_NAME` | sí (si falta, usa SQLite) | no | `staffing` | nombre de la BBDD gestionada |
| `DB_USER` | sí | no | `staffing` | usuario de la BBDD gestionada |
| `DB_PASSWORD` | sí | **sí** | `staffing-local` | contraseña de la BBDD gestionada |
| `DB_HOST` | sí | no | `db` (servicio de compose) | host **interno** de la BBDD (en Cloud Run: `/cloudsql/<CONNECTION_NAME>`) |
| `DB_PORT` | no (defecto `5432`) | no | `5432` | `5432` |
| `DB_CONN_MAX_AGE` | no (defecto `60`) | no | — | `60` (bájalo si el plan gratuito limita conexiones) |
| `PORT` | la inyecta la plataforma | no | — | no la definas: Cloud Run / Render la ponen; el `CMD` ya la lee |

> `DJANGO_ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS` y `CSRF_TRUSTED_ORIGINS` dependen de
> las URLs finales, que solo conoces **tras** el primer despliegue. Orden práctico:
> despliega → copia las URLs → rellena estas tres variables → redespliega.

## Frontend (React + Vite)

| Variable | Cuándo se usa | Secreta | Local | Producción |
|---|---|---|---|---|
| `VITE_API_BASE_URL` | **al compilar** (`npm run build`), no al ejecutar | no (acaba visible en el JS del navegador) | `http://localhost:8000` | URL pública del backend, con `https://` |
| `PORT` | al ejecutar nginx | no | `8080` (defecto de la imagen) | la inyecta la plataforma |

Como `VITE_API_BASE_URL` se incrusta al compilar, **cambiarla exige reconstruir la
imagen del frontend** (`--build-arg` / "build argument" en la plataforma). Nunca pongas
secretos en variables `VITE_*`: cualquiera las ve en el navegador.

## Solo para `compose.prod.yaml` (prueba local de producción)

| Variable | Descripción |
|---|---|
| `DJANGO_SECRET_KEY` | obligatoria; sin ella Compose se niega a arrancar |
| `CORS_ALLOWED_ORIGINS_PROD` | defecto `http://localhost:8080` |
| `CSRF_TRUSTED_ORIGINS` | defecto `http://localhost:8000` |
| `VITE_API_BASE_URL_PROD` | defecto `http://localhost:8000` (build arg del frontend) |
| `CSV_DIR` | carpeta con `Staff.csv` y `Assignments.csv`; defecto `./backend/sample-data` (datos inventados). `CSV_DIR=.` usa los reales |

## Cómo generar y guardar los secretos

Genera `DJANGO_SECRET_KEY` y la contraseña de la BBDD (una para cada entorno):

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
```

| Entorno | Dónde guardarlos |
|---|---|
| Local | `.env` (ignorado por Git; plantilla en `.env.example`, que no contiene valores reales) |
| Render | *Environment* del servicio (o *Environment Group*); marca como secreto |
| Google Cloud Run | Secret Manager y referencia desde el servicio (`--set-secrets`) |

## Qué es secreto y qué no

- **Secreto:** `DJANGO_SECRET_KEY`, `DB_PASSWORD`.
- **Sensible, pero no secreto:** `DB_USER`, `DB_NAME`, `DB_HOST` (no los publiques sin necesidad).
- **Públicas:** `VITE_API_BASE_URL`, `CORS_ALLOWED_ORIGINS`, `DJANGO_ALLOWED_HOSTS`.
- **Datos personales:** `Staff.csv` y `Assignments.csv` reales. No son variables, pero se
  tratan igual que un secreto: fuera de Git, fuera de las imágenes y fuera de la nube
  mientras la app no tenga login. Para practicar usa `backend/sample-data/`.

## Datos de ejemplo

`backend/sample-data/` contiene CSV **inventados** con las mismas columnas que las exportaciones
reales. Se regeneran con:

```bash
python3 scripts/generate_sample_data.py --out backend/sample-data
```

El script es determinista (`--seed`) y calcula las fechas respecto a hoy, para que
siempre haya asignaciones vigentes.
