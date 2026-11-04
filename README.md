# Staffing App

Aplicación React con una API Django para gestionar demandas y perfiles de
candidatos. Los datos se guardan en PostgreSQL; SharePoint, Microsoft Graph y
el inicio de sesión MSAL se han retirado del flujo de la aplicación.

## Arquitectura

```text
Navegador → React → API Django → PostgreSQL
                             └→ Cloud SQL for PostgreSQL (GCP)
```

La API ofrece:

- `GET /api/health/`: comprobación de disponibilidad.
- `GET /api/demands/`: lista demandas.
- `POST /api/demands/`: crea una demanda.
- `GET /api/demands/<code>/`: obtiene el detalle de una demanda.
- `PATCH /api/demands/<code>/`: actualiza sus campos o estado.
- `DELETE /api/demands/<code>/`: elimina la demanda y sus selecciones.
- `GET /api/demands/<code>/candidates/`: lista los perfiles seleccionados.
- `POST /api/demands/<code>/candidates/`: guarda un perfil seleccionado en la
  etapa `initial` o `expanded`.
- `DELETE /api/demands/<code>/candidates/<staff_id>/`: retira una selección.
- `GET /api/demands/<code>/search/?stage=initial|expanded`: búsqueda por etapas
  (ver más abajo). Responde `409 offering_mapping_missing` si el offering de la
  demanda no tiene correspondencia configurada.
- `GET /api/candidates/`: lista perfiles de candidatos activos (sin eliminados).

Los estados de demanda permitidos son `Nueva`, `Búsqueda en curso`,
`En revisión`, `Cubierta` y `Cancelada`. La misma persona no puede añadirse dos
veces a una demanda; si se vuelve a seleccionar se actualiza la etapa.

Los datos de personal y asignaciones se importan de las exportaciones CSV de
SharePoint en las tablas `Staff` y `Assignment`. Las demandas creadas se
guardan por separado en `Demand`. La exportación de Staff no incluye una lista
estructurada de habilidades, por lo que la afinidad por competencias no puede
calcularse con estos datos. El Django Admin permite administrar los tres
conjuntos de datos. Las columnas originales de cada CSV se conservan en
`source_data`; esto incluye datos personales, por lo que se aplican las mismas
precauciones de acceso que a los CSV. La aplicación web no tiene inicio de
sesión ni autorización por usuario: **no se
debe exponer públicamente con datos reales**. Antes de desplegarla en GCP hay
que restringir el acceso a la aplicación/API mediante controles de red o una
solución de identidad aprobada, y definir quién puede administrar los datos.

## Búsqueda de candidatos por etapas

Los candidatos se identifican por `Accenture Id` (el mismo valor que
`Assignment.resource`). El importador rechaza `Accenture Id` duplicados entre
personal activo. Los eliminados (`isDeletedText=yes`) nunca se devuelven.

### Catálogo de staffing (`catalogo_staffing.html`)

Se carga en la migración 0006 y se administra en Django Admin (*Catalog values*,
*Career levels*); `GET /api/catalog/` lo sirve al formulario y la API rechaza
industria, área, localización o nivel que no estén en él (`Remoto` se admite).
Industrias, localizaciones y niveles coinciden exactamente con los valores de
`Staff`, así que filtran sin mapping: nivel = `Career Level Group`, industria =
`Industry` de Staff o de una asignación activa, localización = `Deployment City`.

### Secciones de resultados
- **`initial`**: personal del área/offering de la demanda.
- **`expanded`**: resto del personal con offering.
- **Bolsa transversal**: personal sin offering (`Empty`/vacío); aparece en
  **todas** las búsquedas, en cualquier etapa, con los mismos criterios, y se
  puede seleccionar (`searchStage=transversal`).

El área no es una columna de Staff, por lo que se resuelve con
`CriterionMapping` (Admin). La migración siembra, **por inferencia a partir de
`Role` ("<área> <nivel>") y pendiente de confirmar**: `Enterprise Architecture` →
role que empieza por `Enterprise Architect`, `Technology Strategy` y
`Transformation Excellence` → role con ese prefijo. Sin mapping la búsqueda
devuelve 409. Roles fuera del catálogo (p. ej. `Cloud Advisory`) caen en
`expanded`; "sin offering" = `Role` vacío o `Empty`.

### Disponibilidad
Una persona **no está disponible** cuando la suma de sus asignaciones activas
(`% Assignment`, a la fecha de referencia) alcanza el umbral de su nivel:
Analyst y Consultant 100%, Manager 85.6%, Senior Manager 74.4%, Associate
Director 73.6%, Accenture Leadership 46%. Además, la capacidad libre
(`FTE×100 − asignado`) debe cubrir la ocupación de la demanda (`Flexible` no
filtra). Fecha de referencia: `Inmediata`=hoy, `2 semanas`=+14 días, `1 mes`=+30,
`3 meses`=+90. Asunciones a confirmar: que el umbral se compara con la suma
absoluta de `% Assignment`, y que "alcanza" es `>=`. Si el FTE o algún porcentaje
no es interpretable la persona se excluye (`excluded.unknownCapacity`).
Se desconocen las asignaciones futuras (los CSV solo traen las activas).
No hay habilidades estructuradas, afinidad, puntuación ni LLM; el orden es alfabético.

### Selecciones y estado de la demanda

La etapa de cada selección la calcula el servidor (si el cliente envía
`searchStage` y no coincide → 400). Hay una selección única por demanda y
empleado (reintentar es idempotente). Eliminar una demanda elimina en cascada sus
selecciones. Etapas posibles: `initial`, `expanded`, `transversal`. Transiciones automáticas: primera selección en `Nueva`/`Búsqueda en
curso` → `En revisión`; retirar la última selección en `En revisión` → `Búsqueda
en curso`. Con la demanda `Cubierta` o `Cancelada` no se puede seleccionar ni
retirar (409). Cualquier estado válido puede fijarse manualmente con `PATCH`.

### CV y PowerPoint (bloqueado)

No se implementa localización de CV. `Staff.csv` tiene la columna `Curriculum
Vitae`, pero solo 2 de 322 filas la rellenan, con enlaces de LinkedIn de
personas marcadas como eliminadas; no hay PowerPoint en el repositorio. Falta:
el PowerPoint (o su ubicación), la clave que enlaza cada diapositiva con el
`Accenture Id` en lugar de las iniciales, y una decisión sobre dónde se
almacenarán los CV sin SharePoint.

## Ejecución local con Docker Compose

```bash
cp .env.example .env
docker compose up --build
```

Compose levanta PostgreSQL local, Django y Vite. El backend aplica las
migraciones al arrancar. Abre `http://localhost:5173`; la API queda en
`http://localhost:8000`.

Para administrar personal, asignaciones y demandas localmente:

```bash
docker compose exec backend python manage.py createsuperuser
```

El panel queda disponible en `http://localhost:8000/admin/`.

## Importar las exportaciones CSV

Con los archivos `Staff.csv` y `Assignments.csv` en la raíz del repositorio:

```bash
docker compose exec backend python manage.py import_staffing_csvs \
  --staff-csv /imports/Staff.csv \
  --assignments-csv /imports/Assignments.csv
```

Sin Docker, ejecuta el mismo comando desde `backend/` e indica las rutas a los
CSV. La importación se puede repetir. `Staff` conserva todas las filas e importa
`isDeletedText`; la API solo devuelve personal cuyo indicador no está marcado
como eliminado. `Assignment` solo conserva asignaciones activas: `Sold=True`,
`Confirmed end=False` y la fecha actual incluida entre `Starting Date` y
`Finishing Date`. Cada importación sincroniza esta tabla y elimina las
asignaciones que ya no cumplen la regla. Los registros con fechas ausentes no
se consideran activos.

`--replace` reemplaza todos los registros existentes de personal y
asignaciones; úsalo solo si los CSV son la carga completa que se desea
conservar. En la exportación actual, `Staff` conserva 322 filas y la API
excluye las 183 marcadas como eliminadas. El número de asignaciones activas
varía con la fecha de ejecución. `Demand` queda vacía hasta que se creen
demandas desde la aplicación.

## Despliegue en Google Cloud Platform

- Desplegar el backend Django como servicio en Cloud Run.
- Usar Cloud SQL for PostgreSQL y conectar Cloud Run mediante la conexión
  privada/Cloud SQL attachment de la instancia.
- Configurar `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST` y `DB_PORT` en el
  servicio. Para Cloud Run, `DB_HOST` puede ser `/cloudsql/<INSTANCE_CONNECTION_NAME>`
  si se configura el socket de Cloud SQL. Guardar credenciales en Secret Manager.
- Definir `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=false`, `DJANGO_ALLOWED_HOSTS` y
  `CORS_ALLOWED_ORIGINS` con valores del entorno desplegado.
- Construir y desplegar el frontend con `VITE_API_BASE_URL` apuntando a la URL
  de la API. Esta variable se incorpora durante la compilación de Vite.
- Ejecutar `python manage.py migrate` como paso de despliegue antes de servir
  tráfico; no ejecutar migraciones concurrentemente desde múltiples instancias.
- Restringir el acceso de red y la administración de la base de datos. El
  servicio Django es la única parte de la aplicación que debe conectarse a
  PostgreSQL.

Si `DB_NAME` no está definido, Django usa el archivo SQLite local
`backend/db.sqlite3`; en Compose se configura PostgreSQL.

## Comprobaciones

```bash
cd backend && python manage.py test
cd frontend && npm run lint && npm run build
```

La importación CSV es manual y no sincroniza automáticamente cambios futuros
de SharePoint.
