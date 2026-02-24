# metadata/summary.py
print(">>> metadata/summary.py LOADED")

from google.cloud import bigquery
from google.api_core.exceptions import NotFound

SUMMARY_TABLE_ID = "jira_summary_etl"

SUMMARY_SCHEMA = [
    bigquery.SchemaField("execution_id", "STRING"),
    bigquery.SchemaField("execution_ts", "TIMESTAMP"),
    bigquery.SchemaField("run_id", "STRING"),
    bigquery.SchemaField("execution_mode", "STRING"),

    bigquery.SchemaField("etl_name", "STRING"),
    bigquery.SchemaField("scope", "STRING"),

    bigquery.SchemaField("jira_project_key", "STRING"),
    bigquery.SchemaField("jira_board_id", "INTEGER"),
    bigquery.SchemaField("target_table", "STRING"),
    
    bigquery.SchemaField("jql_applied", "STRING"),
    bigquery.SchemaField("last_updated_seen", "TIMESTAMP"),
    bigquery.SchemaField("batch_size", "INTEGER"),

    bigquery.SchemaField("rows_received", "INTEGER"),
    bigquery.SchemaField("rows_processed", "INTEGER"),
    bigquery.SchemaField("rows_invalid", "INTEGER"),
    bigquery.SchemaField("rows_null_jira_id", "INTEGER"),
    bigquery.SchemaField("rows_null_fecha_actualizacion", "INTEGER"),
    bigquery.SchemaField("rows_duplicate_jira_id", "INTEGER"),
    bigquery.SchemaField("rows_inserted", "INTEGER"),
    bigquery.SchemaField("rows_updated", "INTEGER"),
    bigquery.SchemaField("rows_unchanged", "INTEGER"),
    bigquery.SchemaField("total_rows_bq", "INTEGER"),

    bigquery.SchemaField("batches", "INTEGER"),
    bigquery.SchemaField("api_requests", "INTEGER"),
    bigquery.SchemaField("api_retries_total", "INTEGER"),
    bigquery.SchemaField("api_5xx_events", "INTEGER"),
    bigquery.SchemaField("fallback_to_search_used", "INTEGER"),
    bigquery.SchemaField("rate_limit_events", "INTEGER"),
    bigquery.SchemaField("rate_limit_wait_seconds", "FLOAT"),

    bigquery.SchemaField("status", "STRING"),
    bigquery.SchemaField("execution_seconds", "FLOAT"),
    bigquery.SchemaField("error_message", "STRING"),
]


def ensure_summary_table(
    bq_client: bigquery.Client,
    full_table_id: str,
):
    """
    Crea la tabla de summary si NO existe.
    Si existe, agrega columnas faltantes (evolución de esquema).
    """
    try:
        table = bq_client.get_table(full_table_id)
    except NotFound:
        table = bigquery.Table(full_table_id, schema=SUMMARY_SCHEMA)
        return bq_client.create_table(table)

    existing_fields = {f.name for f in table.schema}
    missing_fields = [field for field in SUMMARY_SCHEMA if field.name not in existing_fields]

    if missing_fields:
        table.schema = list(table.schema) + missing_fields
        table = bq_client.update_table(table, ["schema"])

    return table


def insert_summary(
    bq_client: bigquery.Client,
    full_table_id: str,
    row: dict,
):
    """
    Inserta una fila de summary (1 ejecución = 1 fila)
    """
    errors = bq_client.insert_rows_json(full_table_id, [row])
    if errors:
        raise RuntimeError(f"Error insertando summary ETL: {errors}")
