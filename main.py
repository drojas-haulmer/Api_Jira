# main.py
print(">>> main.py arrancó")

import os
import uuid
from core.logging import get_logger
from core.secrets import get_secret_json
from core.jira_client import JiraClient
from bq.client import get_client
from etl.runner import run_board
from etl.board_resolver import resolve_boards
from metadata.summary import insert_summary
from config.runtime import load_runtime_config

logger = get_logger("jira_etl")


def main():
    run_id = str(uuid.uuid4())[:8]

    logger.info(
        "🚀 Iniciando ejecución Jira ETL",
        extra={"run_id": run_id},
    )

    # ==========================================================
    # 🔁 Detectar modo de ejecución
    # ==========================================================
    is_gcp = bool(os.getenv("RUNTIME_CONFIG_JSON"))
    logger.info(
        "🧭 Modo de ejecución: %s",
        "GCP (Workflow)" if is_gcp else "LOCAL",
        extra={"run_id": run_id},
    )

    # ==========================================================
    # 📥 Cargar runtime config
    # ==========================================================
    runtime = load_runtime_config()
    logger.info(
        "📥 Runtime config cargado",
        extra={"run_id": run_id, "runtime": runtime},
    )

    jira_project_key = runtime["jira_project_key"]
    bq_project_id = runtime.get("bq_project_id", "haulmer-ucloud-production")
    bq_dataset_id = runtime.get("bq_dataset_id", "Jira")
    runtime_boards = runtime.get("boards")

    # ==========================================================
    # 🔐 Secret Manager
    # ==========================================================
    logger.info(
        "🔐 Cargando secreto Jira",
        extra={"run_id": run_id},
    )
    secrets = get_secret_json(bq_project_id, "Jira")

    jira = JiraClient(
        url=secrets["JIRA_URL"],
        user=secrets["JIRA_USER"],
        token=secrets["JIRA_TOKEN"],
        logger=logger,
    )

    # ==========================================================
    # 📊 BigQuery
    # ==========================================================
    bq_client = get_client(bq_project_id)

    # ==========================================================
    # 🧠 Resolver ejecuciones
    # ==========================================================
    boards_to_run = resolve_boards(
        jira=jira,
        jira_project_key=jira_project_key,
        runtime_boards=runtime_boards,
    )

    logger.info(
        "📦 Ejecuciones resueltas",
        extra={"run_id": run_id, "boards": boards_to_run},
    )

    # ==========================================================
    # 🚀 Ejecutar ETL
    # ==========================================================
    for b in boards_to_run:
        logger.info(
            "➡️ Ejecutando ETL",
            extra={
                "run_id": run_id,
                "project": jira_project_key,
                "target_table": b["target_table"],
            },
        )

        run_board(
            target_table=b["target_table"],
            jira_project_key=jira_project_key,
            jira=jira,
            bq_client=bq_client,
            bq_project_id=bq_project_id,
            bq_dataset_id=bq_dataset_id,
            logger=logger,
            summary_writer=lambda row: insert_summary(
                bq_client,
                f"{bq_project_id}.{bq_dataset_id}.jira_summary_etl",
                row,
            ),
        )

    logger.info(
        "🏁 Ejecución finalizada correctamente",
        extra={"run_id": run_id},
    )


if __name__ == "__main__":
    logger.info("🧪 __main__ detectado")
    main()
