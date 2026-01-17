# metadata/summary.py
print(">>> metadata/summary.py LOADED")

from google.cloud import bigquery
from google.api_core.exceptions import NotFound

from google.cloud import bigquery

SUMMARY_TABLE_ID = "jira_summary_etl"

SUMMARY_SCHEMA = [
    bigquery.SchemaField("execution_id", "STRING"),
    bigquery.SchemaField("execution_ts", "TIMESTAMP"),

    bigquery.SchemaField("etl_name", "STRING"),
    bigquery.SchemaField("scope", "STRING"),

    bigquery.SchemaField("jira_project_key", "STRING"),
    bigquery.SchemaField("jira_board_id", "INTEGER"),
    bigquery.SchemaField("target_table", "STRING"),
    
    bigquery.SchemaField("jql_applied", "STRING"),
    bigquery.SchemaField("batch_size", "INTEGER"),

    bigquery.SchemaField("rows_processed", "INTEGER"),
    bigquery.SchemaField("rows_inserted", "INTEGER"),
    bigquery.SchemaField("rows_updated", "INTEGER"),
    bigquery.SchemaField("total_rows_bq", "INTEGER"),

    bigquery.SchemaField("batches", "INTEGER"),
    bigquery.SchemaField("api_requests", "INTEGER"),
    bigquery.SchemaField("rate_limit_events", "INTEGER"),
    bigquery.SchemaField("rate_limit_wait_seconds", "FLOAT"),

    bigquery.SchemaField("status", "STRING"),
    bigquery.SchemaField("execution_seconds", "FLOAT"),
    bigquery.SchemaField("error_message", "STRING"),
]


def ensure_summary_table(bq_client, full_table_id: str):
    try:
        bq_client.get_table(full_table_id)
    except Exception:
        table = bigquery.Table(full_table_id, schema=SUMMARY_SCHEMA)
        bq_client.create_table(table)



def ensure_summary_table(
    bq_client: bigquery.Client,
    full_table_id: str,
):
    """
    Crea la tabla de summary si NO existe.
    """
    try:
        bq_client.get_table(full_table_id)
        return
    except NotFound:
        table = bigquery.Table(full_table_id, schema=SUMMARY_SCHEMA)
        table = bq_client.create_table(table)
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
