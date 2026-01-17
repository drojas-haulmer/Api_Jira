# core/secrets.py
import json
from google.cloud import secretmanager

def get_secret_json(project_id: str, secret_id: str) -> dict:
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
    resp = client.access_secret_version(name=name)
    return json.loads(resp.payload.data.decode("UTF-8"))
