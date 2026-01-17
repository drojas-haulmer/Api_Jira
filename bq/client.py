# bq/client.py
from google.cloud import bigquery
from google.api_core.exceptions import NotFound

def get_client(project_id: str) -> bigquery.Client:
    return bigquery.Client(project=project_id)

def ensure_dataset(client, project_id: str, dataset_id: str):
    ref = f"{project_id}.{dataset_id}"
    try:
        client.get_dataset(ref)
    except NotFound:
        client.create_dataset(bigquery.Dataset(ref))

def ensure_table(client, full_table: str, schema):
    try:
        client.get_table(full_table)
    except NotFound:
        client.create_table(bigquery.Table(full_table, schema=schema))

def count_rows(client, full_table: str) -> int:
    q = f"SELECT COUNT(*) c FROM `{full_table}`"
    return int(next(client.query(q).result()).c)
