# etl/transform.py
import json
from datetime import datetime

def parse_dt(dt):
    if not dt:
        return None
    return datetime.fromisoformat(dt.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M:%S")

def transform_issue(issue: dict) -> dict:
    fields = issue.get("fields", {})
    return {
        "jira_id": issue.get("id"),
        "clave": issue.get("key"),
        "fecha_creacion": parse_dt(fields.get("created")),
        "fecha_actualizacion": parse_dt(fields.get("updated")),
        "raw_json": json.dumps(issue, ensure_ascii=False),
    }
