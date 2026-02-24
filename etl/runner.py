# etl/runner.py
print(">>> etl/runner.py LOADED")

import uuid
from time import perf_counter
from datetime import datetime, timezone

from etl.transform import transform_issue
from etl.merge import RAW_SCHEMA, merge_with_metrics
from etl.quality import validate_and_dedupe_rows
from bq.client import ensure_dataset, ensure_table, count_rows
from bq.utils import get_max_updated_at
from metadata.summary import ensure_summary_table, SUMMARY_TABLE_ID


# ==========================================================
# 🧠 Utils
# ==========================================================
def format_jira_datetime_for_jql(dt: datetime) -> str:
    """
    EXACTAMENTE el formato que Jira acepta y que el script funcional usa:
    yyyy-MM-dd HH:mm
    """
    return dt.strftime("%Y-%m-%d %H:%M")


# ==========================================================
# 🚀 MAIN ETL
# ==========================================================
def run_board(
    *,
    target_table: str,
    jira_project_key: str,
    scope: str,
    jira_board_id: int | None,
    run_id: str,
    execution_mode: str,
    jira,
    bq_client,
    bq_project_id: str,
    bq_dataset_id: str,
    logger,
    summary_writer,
):
    print(">>> run_board() ENTERED PROJECT")

    exec_id = str(uuid.uuid4())
    exec_ts = datetime.now(timezone.utc)
    t0 = perf_counter()

    metrics = {
        "rows_received": 0,
        "rows_processed": 0,
        "rows_invalid": 0,
        "rows_null_jira_id": 0,
        "rows_null_fecha_actualizacion": 0,
        "rows_duplicate_jira_id": 0,
        "rows_inserted": 0,
        "rows_updated": 0,
        "rows_unchanged": 0,
        "batches": 0,
        "api_requests": 0,
        "rate_limit_events": 0,
        "rate_limit_wait_seconds": 0.0,
        "api_retries_total": 0,
        "api_5xx_events": 0,
        "fallback_to_search_used": 0,
    }

    status = "SUCCESS"
    error_message = None
    total_rows = None
    jql = None
    last_updated = None

    try:
        # ------------------------------------------------------
        # 🏗 Infra BigQuery
        # ------------------------------------------------------
        logger.info("🏗 Ensuring dataset & tables")

        ensure_dataset(bq_client, bq_project_id, bq_dataset_id)

        summary_full = f"{bq_project_id}.{bq_dataset_id}.{SUMMARY_TABLE_ID}"
        ensure_summary_table(bq_client, summary_full)

        raw_full = f"{bq_project_id}.{bq_dataset_id}.{target_table}"
        ensure_table(bq_client, raw_full, RAW_SCHEMA)

        # ------------------------------------------------------
        # 🕒 Construcción JQL (idéntica al script funcional)
        # ------------------------------------------------------
        last_updated = get_max_updated_at(bq_client, raw_full)

        if last_updated:
            last_updated = last_updated.replace(second=0, microsecond=0)
            jira_dt = format_jira_datetime_for_jql(last_updated)

            jql = (
                f'project={jira_project_key} '
                f'AND updated >= "{jira_dt}" '
                f'ORDER BY updated ASC'
            )

            logger.info("🔄 Incremental load")
            logger.info("🧠 last_updated_raw = %s", last_updated)
            logger.info("🧠 jira_dt_for_jql = %s", jira_dt)
        else:
            jql = f"project={jira_project_key} ORDER BY updated ASC"
            logger.info("🆕 Full load (no previous data)")

        logger.info("🔎 JQL FINAL → %s", jql)

        # ------------------------------------------------------
        # 📥 Fetch Jira
        # ------------------------------------------------------
        logger.info(
            "🚀 Calling JiraClient.fetch_issues_by_project | "
            "project_key=%s | batch_size=%s",
            jira_project_key,
            100,
        )

        issue_generator = jira.fetch_issues_by_project(
            project_key=jira_project_key,   # 🔥 CLAVE
            jql=jql,
            batch_size=100,
            stats=metrics,
        )

        # ------------------------------------------------------
        # 🔁 Loop batches
        # ------------------------------------------------------
        for issues in issue_generator:
            metrics["batches"] += 1

            logger.info(
                "📦 Batch %d received | issues=%d",
                metrics["batches"],
                len(issues),
            )

            raw_rows = [transform_issue(i) for i in issues]
            metrics["rows_received"] += len(raw_rows)

            rows, quality = validate_and_dedupe_rows(raw_rows)

            metrics["rows_invalid"] += quality["rows_invalid"]
            metrics["rows_null_jira_id"] += quality["rows_null_jira_id"]
            metrics["rows_null_fecha_actualizacion"] += quality["rows_null_fecha_actualizacion"]
            metrics["rows_duplicate_jira_id"] += quality["rows_duplicate_jira_id"]
            metrics["rows_processed"] += quality["rows_valid"]

            merge_metrics = merge_with_metrics(
                bq_client,
                bq_project_id,
                bq_dataset_id,
                target_table,
                rows,
            )

            metrics["rows_inserted"] += merge_metrics["inserted"]
            metrics["rows_updated"] += merge_metrics["updated"]
            metrics["rows_unchanged"] += merge_metrics["unchanged"]

            logger.info(
                "✅ Batch %d merged | inserted=%d | updated=%d | unchanged=%d | valid=%d | invalid=%d",
                metrics["batches"],
                merge_metrics["inserted"],
                merge_metrics["updated"],
                merge_metrics["unchanged"],
                quality["rows_valid"],
                quality["rows_invalid"],
            )

        total_rows = count_rows(bq_client, raw_full)

    except Exception as e:
        status = "FAILED"
        error_message = str(e)
        logger.exception("❌ run_board FAILED")

    # ------------------------------------------------------
    # 🧾 Summary
    # ------------------------------------------------------
    elapsed = perf_counter() - t0

    summary_writer({
        "execution_id": exec_id,
        "execution_ts": exec_ts.isoformat(),
        "run_id": run_id,
        "execution_mode": execution_mode,
        "etl_name": f"{jira_project_key}_{target_table}",
        "scope": scope,
        "jira_project_key": jira_project_key,
        "jira_board_id": jira_board_id,
        "target_table": target_table,
        "jql_applied": jql,
        "last_updated_seen": last_updated.isoformat() if isinstance(last_updated, datetime) else None,
        "batch_size": 100,
        "rows_received": metrics["rows_received"],
        "rows_processed": metrics["rows_processed"],
        "rows_invalid": metrics["rows_invalid"],
        "rows_null_jira_id": metrics["rows_null_jira_id"],
        "rows_null_fecha_actualizacion": metrics["rows_null_fecha_actualizacion"],
        "rows_duplicate_jira_id": metrics["rows_duplicate_jira_id"],
        "rows_inserted": metrics["rows_inserted"],
        "rows_updated": metrics["rows_updated"],
        "rows_unchanged": metrics["rows_unchanged"],
        "total_rows_bq": total_rows,
        "batches": metrics["batches"],
        "api_requests": metrics["api_requests"],
        "api_retries_total": metrics["api_retries_total"],
        "api_5xx_events": metrics["api_5xx_events"],
        "fallback_to_search_used": metrics["fallback_to_search_used"],
        "rate_limit_events": metrics["rate_limit_events"],
        "rate_limit_wait_seconds": metrics["rate_limit_wait_seconds"],
        "status": status,
        "execution_seconds": elapsed,
        "error_message": error_message,
    })

    logger.info(
        "🏁 DONE | status=%s | processed=%d | batches=%d | %.2fs",
        status,
        metrics["rows_processed"],
        metrics["batches"],
        elapsed,
    )

    return {
        "status": status,
        "target_table": target_table,
        "rows_received": metrics["rows_received"],
        "rows_processed": metrics["rows_processed"],
        "rows_invalid": metrics["rows_invalid"],
        "rows_inserted": metrics["rows_inserted"],
        "rows_updated": metrics["rows_updated"],
        "rows_unchanged": metrics["rows_unchanged"],
    }
