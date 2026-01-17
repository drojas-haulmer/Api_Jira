# bq/utils.py
from google.cloud import bigquery

def get_max_updated_at(bq_client, full_table_id: str) -> str | None:
    query = f"""
        SELECT
          MAX(fecha_actualizacion) AS max_fecha
        FROM `{full_table_id}`
    """
    rows = list(bq_client.query(query).result())
    if rows and rows[0].max_fecha:
        return rows[0].max_fecha.strftime("%Y-%m-%d %H:%M:%S")
    return None
