# Jira ETL – API y pipeline de datos

Pipeline ETL que extrae issues de **Jira** (REST API), los transforma y carga en **BigQuery**. Puede ejecutarse en **local** o en **Google Cloud (GCP)** mediante un Workflow que crea una VM efímera, ejecuta el ETL y la elimina.

---

## Índice

- [Descripción general](#descripción-general)
- [Arquitectura y flujo](#arquitectura-y-flujo)
- [Requisitos](#requisitos)
- [Cómo levantar la API / ETL en local](#cómo-levantar-la-api--etl-en-local)
- [Cómo se levanta en GCP (producción)](#cómo-se-levanta-en-gcp-producción)
- [Configuración](#configuración)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Tablas en BigQuery](#tablas-en-bigquery)
- [Secret Manager y credenciales](#secret-manager-y-credenciales)

---

## Descripción general

- **Origen:** Jira (REST API v3, endpoint `search/jql`).
- **Destino:** BigQuery (dataset configurable, tablas raw por proyecto/board y tabla de resumen de ejecuciones).
- **Modos:** local (archivo `boards.json`) o GCP (variable de entorno `RUNTIME_CONFIG_JSON` + Workflow que lanza una VM con script de arranque).

No es un servidor HTTP: es un **script ETL** que se ejecuta una vez por invocación (`python main.py`). En GCP, cada ejecución del Workflow = una VM nueva → clonar repo → ejecutar ETL → borrar VM.

---

## Arquitectura y flujo

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           MODO LOCAL                                     │
│  boards.json → main.py → Jira API + BigQuery (credenciales locales)     │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                           MODO GCP (Producción)                          │
│  Workflow → Secret Manager (GitHub token)                                │
│          → Crear VM (metadata: RUNTIME_CONFIG_JSON, GITHUB_TOKEN)        │
│          → startup-script-url → startup.sh                              │
│          → Clonar Api_Jira → venv → pip install → python main.py         │
│          → Secret Manager (Jira) + BigQuery                              │
│          → VM se autodestruye (DELETE sobre sí misma)                    │
└─────────────────────────────────────────────────────────────────────────┘
```

**Flujo del ETL (común a ambos modos):**

1. Cargar **runtime config** (`RUNTIME_CONFIG_JSON` o `boards.json`).
2. Obtener credenciales Jira desde **Secret Manager** (secreto `Jira` en JSON: `JIRA_URL`, `JIRA_USER`, `JIRA_TOKEN`).
3. **Resolver alcance:** por proyecto (una tabla tipo `{project}_project_raw`) o por boards explícitos (`board_id` + `target_table`).
4. Para cada alcance:
   - Crear/asegurar dataset y tablas en BigQuery.
   - Construir JQL (incremental si hay `fecha_actualizacion` previa en BQ).
   - Paginar issues vía `POST /rest/api/3/search/jql` (con `changelog`).
   - Transformar, merge (INSERT/UPDATE) en tabla raw y escribir fila en tabla de resumen (`jira_summary_etl`).
5. Finalizar (en GCP, después de esto el `startup.sh` llama al API de Compute para eliminar la VM).

---

## Requisitos

- **Python:** 3.10+ (recomendado 3.11+).
- **Cuenta GCP** (para ejecución en nube y para Secret Manager / BigQuery también en local si usas BQ).
- **Credenciales:**
  - Local: Application Default Credentials (`gcloud auth application-default login`) con acceso a Secret Manager y BigQuery.
  - GCP: VM con service account (en el workflow: `bigquery@...`) con permisos a Secret Manager, BigQuery y Compute (para autodestrucción).

Dependencias Python: ver `requirements.txt` (p. ej. `requests`, `google-cloud-bigquery`, `google-cloud-secret-manager`, `google-cloud-logging`, etc.).

---

## Cómo levantar la API / ETL en local

No hay servidor HTTP: se “levanta” ejecutando el script una vez.

### 1. Clonar y entorno virtual

```bash
git clone https://github.com/drojas-haulmer/Api_Jira.git
cd Api_Jira
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Credenciales GCP (para Secret Manager y BigQuery)

```bash
gcloud auth application-default login
```

Asegúrate de que la cuenta tenga acceso al proyecto donde está el secreto `Jira` y al proyecto/dataset de BigQuery.

### 3. Configuración de ejecución (modo local)

Crea en la raíz del repo un archivo **`boards.json`** (o usa solo proyecto, ver más abajo). Ejemplo por proyecto (una sola tabla por proyecto):

```json
{
  "jira_project_key": "SAP",
  "bq_project_id": "haulmer-ucloud-production",
  "bq_dataset_id": "Jira"
}
```

Ejemplo con boards explícitos:

```json
{
  "jira_project_key": "SAP",
  "bq_project_id": "haulmer-ucloud-production",
  "bq_dataset_id": "Jira",
  "boards": [
    { "board_id": 123, "target_table": "sap_board_123_raw" },
    { "board_id": 456, "target_table": "sap_board_456_raw" }
  ]
}
```

- Si no pones `boards` o está vacío, se usa una sola ejecución a nivel de **proyecto** con tabla `{jira_project_key}_project_raw`.
- Si pones `boards`, solo se ejecutan esos y cada uno debe tener `board_id` y `target_table`.

### 4. Ejecutar el ETL

```bash
python main.py
```

La primera vez que se ejecuta, el código:

- Carga el runtime desde `boards.json`.
- Lee el secreto `Jira` de Secret Manager (proyecto `bq_project_id`).
- Crea/usa el dataset y las tablas en BigQuery y ejecuta el ETL (JQL → transform → merge) y escribe el resumen en `jira_summary_etl`.

Resumen: **“levantar la API” en local = tener `boards.json` + credenciales GCP y ejecutar `python main.py`.**

---

## Cómo se levanta en GCP (producción)

En producción no se “levanta” un servidor: un **Workflow de GCP** orquesta la ejecución puntual del ETL usando una VM efímera.

### Visión general del workflow

1. El Workflow obtiene el **token de GitHub** desde Secret Manager.
2. Crea una **VM** en la zona indicada, con:
   - Imagen: Debian 12.
   - Metadata:
     - `GITHUB_TOKEN`: token para clonar el repo.
     - `RUNTIME_CONFIG_JSON`: JSON con `jira_project_key`, `bq_project_id`, `bq_dataset_id` y opcionalmente `boards`.
   - **Startup script** por URL:  
     `https://raw.githubusercontent.com/drojas-haulmer/Api_Jira/main/scripts/startup.sh`
3. Al arrancar, la VM:
   - Lee metadata (proyecto, zona, nombre, `RUNTIME_CONFIG_JSON`, `GITHUB_TOKEN`).
   - Instala dependencias (git, python3, venv, pip, etc.).
   - Clona el repo `Api_Jira` (con el token).
   - Crea `venv`, instala `requirements.txt`.
   - Exporta `RUNTIME_CONFIG_JSON` y ejecuta **`python main.py`**.
   - Si el ETL termina bien, la VM se **autodestruye** (DELETE a la API de Compute sobre sí misma).

### Definición del Workflow (resumida)

Parámetros típicos del workflow:

| Parámetro        | Valor ejemplo                          |
|------------------|----------------------------------------|
| `VM_NAME`        | `jira-etl-sap-project`                 |
| `PROJECT_ID`     | `haulmer-ucloud-production`            |
| `ZONE`           | `us-east1-b`                           |
| `MACHINE_TYPE`   | `n2d-standard-4`                       |
| `GITHUB_SECRET`  | `projects/.../secrets/github-drojas-haulmer/versions/latest` |

Pasos principales:

1. **Log inicial** (opcional).
2. **init_vars**: definir las variables anteriores.
3. **get_github_token**: `googleapis.secretmanager.v1.projects.secrets.versions.access` con `name: ${GITHUB_SECRET}` → `github_token`.
4. **create_vm**: `googleapis.compute.v1.instances.insert` con:
   - `project`, `zone`, `name`, `machineType`.
   - `serviceAccounts` (p. ej. `bigquery@...`) con scope `cloud-platform`.
   - Disco boot Debian 12, 100 GB, `autoDelete: true`.
   - Red por defecto con NAT.
   - Metadata:
     - `GITHUB_TOKEN`: valor del token (decodificado desde `github_token.payload.data`).
     - `RUNTIME_CONFIG_JSON`: string JSON, por ejemplo:  
       `{"jira_project_key":"SAP","bq_project_id":"haulmer-ucloud-production","bq_dataset_id":"Jira"}`.
     - `startup-script-url`:  
       `https://raw.githubusercontent.com/drojas-haulmer/Api_Jira/main/scripts/startup.sh`
5. **Log final** (opcional).

El script `scripts/startup.sh` es el que realmente “levanta” el ETL dentro de la VM (instalación, clonado, `python main.py`) y luego elimina la VM.

### Cómo ejecutar el workflow

- Desde **Google Cloud Console:** Workflows → seleccionar el workflow → “Ejecutar”.
- Desde **gcloud:**  
  `gcloud workflows run <WORKFLOW_NAME> --location=<REGION>`  
  (ajustando nombre y región según tu despliegue).

Cada ejecución = una VM nueva → un run del ETL → VM borrada. No hay API HTTP persistente en GCP.

---

## Configuración

### Runtime config (común)

- **`jira_project_key`** (obligatorio): Clave del proyecto en Jira (ej. `SAP`).
- **`bq_project_id`** (opcional): Proyecto GCP de BigQuery. Por defecto `haulmer-ucloud-production`.
- **`bq_dataset_id`** (opcional): Dataset de BigQuery. Por defecto `Jira`.
- **`boards`** (opcional): Lista de `{ "board_id": number, "target_table": "string" }`. Si no se envía o está vacía, se ejecuta un solo “board” a nivel de proyecto con tabla `{jira_project_key}_project_raw`.

### Dónde se define

- **Local:** archivo `boards.json` en la raíz del repo.
- **GCP:** variable de entorno `RUNTIME_CONFIG_JSON` (string JSON), inyectada por el Workflow vía metadata de la VM y leída en `startup.sh` con `curl` a la metadata.

El código en `config/runtime.py` carga esta config (prioridad: env `RUNTIME_CONFIG_JSON` > `boards.json`) y falla si no hay ninguna.

---

## Estructura del proyecto

```
Api_Jira/
├── main.py                 # Punto de entrada: carga config, secrets, resuelve boards, ejecuta ETL
├── requirements.txt        # Dependencias Python
├── boards.json             # (local) Config de runtime; no versionado o ejemplo en .gitignore
├── config/
│   ├── runtime.py          # Carga RUNTIME_CONFIG_JSON o boards.json
│   └── settings.py         # Ajustes adicionales si existen
├── core/
│   ├── logging.py          # Logger (Cloud Logging en GCP, consola en local)
│   ├── secrets.py          # Lectura de Secret Manager (get_secret_json)
│   └── jira_client.py      # Cliente Jira (REST search/jql, paginación, changelog)
├── bq/
│   ├── client.py           # Cliente BigQuery, ensure_dataset, ensure_table, count_rows
│   └── utils.py            # get_max_updated_at, etc.
├── etl/
│   ├── runner.py           # run_board: orquesta ETL por board/proyecto, JQL, merge, métricas
│   ├── board_resolver.py   # resolve_boards: proyecto vs lista explícita de boards
│   ├── transform.py        # transform_issue: raw Jira → filas para BQ
│   └── merge.py            # merge_with_metrics, RAW_SCHEMA, MERGE en BQ
├── metadata/
│   └── summary.py          # Tabla jira_summary_etl, insert_summary
└── scripts/
    └── startup.sh          # Script de arranque en la VM GCP (deps, clone, venv, main.py, autodestrucción)
```

---

## Tablas en BigQuery

- **Tablas raw por alcance:** una por proyecto o por board, con nombre configurado (ej. `SAP_project_raw` o el `target_table` de cada board). Esquema típico: `jira_id`, `clave`, `fecha_creacion`, `fecha_actualizacion`, `raw_json` (definido en `etl/merge.py` como `RAW_SCHEMA`).
- **Tabla de resumen:** `jira_summary_etl` en el mismo dataset. Guarda una fila por ejecución de ETL (execution_id, execution_ts, etl_name, scope, jira_project_key, target_table, jql, filas procesadas/insertadas/actualizadas, batches, status, tiempo, errores, etc.). Definida en `metadata/summary.py`.

El dataset se crea si no existe (`ensure_dataset`). Las tablas se crean con el esquema correspondiente si no existen.

---

## Secret Manager y credenciales

- **Secreto `Jira`** (usado por el ETL): debe ser un JSON con:
  - `JIRA_URL`: base URL de Jira (ej. `https://tu-empresa.atlassian.net`).
  - `JIRA_USER`: usuario (email o usuario de API).
  - `JIRA_TOKEN`: token o contraseña de aplicación.

- **Secreto GitHub** (solo para el Workflow): usado para clonar el repo en la VM. El Workflow lo referencia como `GITHUB_SECRET` (versión `latest`) y lo inyecta en la metadata de la VM como `GITHUB_TOKEN`.

En local, la aplicación usa las credenciales por defecto de GCP (`gcloud auth application-default login`); en la VM, la cuenta de servicio configurada en el Workflow debe tener permisos sobre Secret Manager, BigQuery y Compute (para el DELETE de la VM).

---

## Resumen rápido

| Entorno   | Cómo se “levanta” |
|----------|--------------------|
| **Local** | `boards.json` + `gcloud auth application-default login` + `python main.py` |
| **GCP**   | Ejecutar el Workflow → crea VM → `startup.sh` instala, clona, ejecuta `python main.py` → VM se autodestruye |

No hay API HTTP que quede levantada: es un ETL por ejecución (batch).
