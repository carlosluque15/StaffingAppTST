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
- `GET /api/assignments/?scope=active|all`: asignaciones enlazadas con su persona
  (nivel, industria con respaldo de Staff). `active` (por defecto) solo las vigentes
  hoy; `all` incluye el histórico y las personas de baja (`personDeleted`). La pestaña
  «Asignaciones» las agrupa en el navegador por proyecto, cliente, career level o industria.
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
`Industry` de Staff o de una asignación activa (quien no tiene ninguna industria
conocida no se excluye: se muestra como «Industria sin datos»; solo se excluye si
tiene industria y ninguna coincide), localización = `Deployment City`.

### Secciones de resultados
El offering de una demanda es la **Organization Unit** de `Staff`.
- **`initial`**: personal de la Organization Unit de la demanda.
- **`expanded`**: personal de otras Organization Units, salvo analistas.
- **Bolsa transversal**: **analistas** (`Career Level Group = Analyst`) de otras
  Organization Units; aparece en **todas** las búsquedas, en cualquier etapa, con
  los mismos criterios salvo el nivel de la demanda (no se aplica), y se puede
  seleccionar (`searchStage=transversal`). La UI ofrece filtros locales.

El catálogo de offerings se alimenta de los valores distintos de
`Organization Unit` al importar (migración 0008 siembra los principales) y cada
valor se mapea a sí mismo en `CriterionMapping` (`organization_unit`). Las demandas
creadas con las áreas antiguas (Enterprise Architecture, Technology Strategy,
Transformation Excellence) deben reeditarse con una Organization Unit; mientras
tanto su búsqueda devuelve 409. El rol de la demanda es opcional.

### Importación de CSV
Los `Accenture Id` repetidos entre activos se deduplican (se conserva la fila con
más columnas rellenas, la última si empatan) y los activos sin id se omiten, con
avisos en stderr y «N duplicados descartados» en el resumen. Si la importación
falla en `docker compose up`, el backend arranca igualmente con los datos previos.

### Disponibilidad
La página Talento muestra la columna «Obligatorio» (umbral de su nivel) con
«Cumple»/«Pendiente» según su ocupación de hoy.

Una persona **no está disponible** cuando la suma de sus asignaciones activas
(`% Assignment`, a la fecha de referencia) alcanza el umbral de su nivel:
Analyst y Consultant 100%, Manager 85.6%, Senior Manager 74.4%, Associate
Director 73.6%, Accenture Leadership 46%. Además, la capacidad libre
(`FTE×100 − asignado`) debe cubrir la ocupación de la demanda (`Flexible` no
filtra). Fecha de referencia: la fecha de inicio de la demanda (`startDate`), o hoy si
ya pasó. Asunciones a confirmar: que el umbral se compara con la suma
absoluta de `% Assignment`, y que "alcanza" es `>=`. Si el FTE o algún porcentaje
no es interpretable la persona se excluye (`excluded.unknownCapacity`).
Se desconocen las asignaciones futuras (los CSV solo traen las activas).
No hay habilidades estructuradas, afinidad, puntuación ni LLM; el orden es alfabético.

Las habilidades clave quedan fuera del formulario de demanda hasta integrar la IA. El campo `skills` se conserva en la API y la base de datos (opcional, por defecto `[]`), de modo que las demandas existentes no pierden datos.

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

## Informes

La pestaña **Informes** descarga tablas de la BBDD en CSV (UTF-8 con BOM, para Excel):
`GET /api/reports/staff.csv` y `GET /api/reports/assignments.csv`. Usan las columnas
originales de los CSV importados (`source_data`) e incluyen personas borradas. Los valores
que empiezan por `=`, `+`, `-` o `@` (y no son numéricos) se prefijan con `'` contra
inyección de fórmulas. Nuevos informes van bajo el prefijo `reports/`.

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

## Datos de ejemplo y variables de entorno

`docker compose up` importa por defecto `backend/sample-data/` (personal y asignaciones
**inventados**, mismas columnas que los CSV reales; se regeneran con
`python3 scripts/generate_sample_data.py`). Para usar los CSV reales de la raíz:
`CSV_DIR=. docker compose up`. Todas las variables y dónde guardar cada secreto:
[docs/VARIABLES.md](docs/VARIABLES.md). Prueba de las imágenes de producción:
`docker compose -f compose.prod.yaml up --build`.

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
