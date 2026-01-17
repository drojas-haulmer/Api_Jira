# etl/merge.py
import time
from google.cloud import bigquery

RAW_SCHEMA = [
    bigquery.SchemaField("jira_id", "STRING"),
    bigquery.SchemaField("clave", "STRING"),
    bigquery.SchemaField("fecha_creacion", "TIMESTAMP"),
    bigquery.SchemaField("fecha_actualizacion", "TIMESTAMP"),
    bigquery.SchemaField("raw_json", "STRING"),
]

def merge_with_metrics(client, project_id, dataset_id, table_id, rows):
    if not rows:
        return {"inserted": 0, "updated": 0}

    temp = f"{dataset_id}.tmp_{table_id}_{int(time.time())}"
    full = f"{project_id}.{dataset_id}.{table_id}"
    temp_full = f"{project_id}.{temp}"

    client.create_table(bigquery.Table(temp_full, schema=RAW_SCHEMA), exists_ok=True)
    client.load_table_from_json(rows, temp_full).result()

    inserted = next(client.query(f"""
      SELECT COUNT(*) c FROM `{temp_full}` s
      LEFT JOIN `{full}` t ON t.jira_id = s.jira_id
      WHERE t.jira_id IS NULL
    """).result()).c

    updated = next(client.query(f"""
      SELECT COUNT(*) c FROM `{temp_full}` s
      JOIN `{full}` t ON t.jira_id = s.jira_id
      WHERE TIMESTAMP(s.fecha_actualizacion) > t.fecha_actualizacion
    """).result()).c

    client.query(f"""
      MERGE `{full}` T
      USING `{temp_full}` S
      ON T.jira_id = S.jira_id
      WHEN MATCHED AND TIMESTAMP(S.fecha_actualizacion) > T.fecha_actualizacion THEN
        UPDATE SET clave=S.clave,
                   fecha_creacion=TIMESTAMP(S.fecha_creacion),
                   fecha_actualizacion=TIMESTAMP(S.fecha_actualizacion),
                   raw_json=S.raw_json
      WHEN NOT MATCHED THEN
        INSERT ROW
    """).result()

    client.delete_table(temp_full, not_found_ok=True)
    return {"inserted": int(inserted), "updated": int(updated)}
