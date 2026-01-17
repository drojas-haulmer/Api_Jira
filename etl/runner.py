# etl/runner.py
print(">>> etl/runner.py LOADED")

import uuid
from time import perf_counter
from datetime import datetime, timezone

from etl.transform import transform_issue
from etl.merge import RAW_SCHEMA, merge_with_metrics
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
        "rows_processed": 0,
        "rows_inserted": 0,
        "rows_updated": 0,
        "batches": 0,
        "api_requests": 0,
        "rate_limit_events": 0,
        "rate_limit_wait_seconds": 0.0,
    }

    status = "SUCCESS"
    error_message = None
    total_rows = None
    jql = None

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
            if isinstance(last_updated, str):
                last_updated = datetime.fromisoformat(last_updated)

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

            rows = [transform_issue(i) for i in issues]
            metrics["rows_processed"] += len(rows)

            merge_metrics = merge_with_metrics(
                bq_client,
                bq_project_id,
                bq_dataset_id,
                target_table,
                rows,
            )

            metrics["rows_inserted"] += merge_metrics["inserted"]
            metrics["rows_updated"] += merge_metrics["updated"]

            logger.info(
                "✅ Batch %d merged | inserted=%d | updated=%d | total_processed=%d",
                metrics["batches"],
                merge_metrics["inserted"],
                merge_metrics["updated"],
                metrics["rows_processed"],
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
        "etl_name": f"{jira_project_key}_{target_table}",
        "scope": "PROJECT",
        "jira_project_key": jira_project_key,
        "jira_board_id": None,
        "target_table": target_table,
        "jql_applied": jql,
        "batch_size": 100,
        "rows_processed": metrics["rows_processed"],
        "rows_inserted": metrics["rows_inserted"],
        "rows_updated": metrics["rows_updated"],
        "total_rows_bq": total_rows,
        "batches": metrics["batches"],
        "api_requests": metrics["api_requests"],
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
