from datetime import datetime


def _to_datetime(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def validate_and_dedupe_rows(rows):
    """
    Valida filas de entrada y elimina duplicados por jira_id.
    En duplicados conserva la fila con fecha_actualizacion mas nueva.
    """
    stats = {
        "rows_received": len(rows),
        "rows_valid": 0,
        "rows_invalid": 0,
        "rows_null_jira_id": 0,
        "rows_null_fecha_actualizacion": 0,
        "rows_duplicate_jira_id": 0,
    }

    valid = {}

    for row in rows:
        jira_id = row.get("jira_id")
        updated_raw = row.get("fecha_actualizacion")
        updated_dt = _to_datetime(updated_raw)

        if not jira_id:
            stats["rows_null_jira_id"] += 1
            stats["rows_invalid"] += 1
            continue

        if updated_dt is None:
            stats["rows_null_fecha_actualizacion"] += 1
            stats["rows_invalid"] += 1
            continue

        current = valid.get(jira_id)
        if current is None:
            valid[jira_id] = (row, updated_dt)
            continue

        stats["rows_duplicate_jira_id"] += 1
        if updated_dt >= current[1]:
            valid[jira_id] = (row, updated_dt)

    deduped = [value[0] for value in valid.values()]
    stats["rows_valid"] = len(deduped)
    return deduped, stats
