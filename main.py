# main.py
print(">>> main.py arrancó")

import os
from core.logging import get_logger
from core.secrets import get_secret_json
from core.jira_client import JiraClient
from bq.client import get_client
from etl.runner import run_board
from etl.board_resolver import resolve_boards
from metadata.summary import insert_summary
from config.runtime import load_runtime_config

logger = get_logger("jira_etl")
logger.warning("🔥 Logger inicializado correctamente")


def main():
    logger.info("🚀 Entrando a main()")

    # ==========================================================
    # 🔁 Detectar modo de ejecución
    # ==========================================================
    is_gcp = bool(os.getenv("RUNTIME_CONFIG_JSON"))
    logger.info(
        "🧭 Modo de ejecución detectado: %s",
        "GCP (Workflow)" if is_gcp else "LOCAL",
    )

    # ==========================================================
    # 📥 Cargar runtime config
    # ==========================================================
    runtime = load_runtime_config()
    logger.info("📥 Runtime config cargado: %s", runtime)

    jira_project_key = runtime["jira_project_key"]
    bq_project_id = runtime.get("bq_project_id", "haulmer-ucloud-production")
    bq_dataset_id = runtime.get("bq_dataset_id", "Jira")
    runtime_boards = runtime.get("boards")

    # ==========================================================
    # 🔐 Secret Manager
    # ==========================================================
    logger.info("🔐 Cargando secreto Jira desde Secret Manager")
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
    # 🧠 Resolver ejecuciones (PROJECT only)
    # ==========================================================
    boards_to_run = resolve_boards(
        jira=jira,
        jira_project_key=jira_project_key,
        runtime_boards=runtime_boards,
    )

    logger.info("📦 Ejecuciones a realizar: %s", boards_to_run)

    # ==========================================================
    # 🚀 Ejecutar ETL
    # ==========================================================
    for b in boards_to_run:
        logger.info(
            "➡️ Ejecutando ETL | project=%s | table=%s",
            jira_project_key,
            b["target_table"],
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

    logger.info("🏁 main() finalizado correctamente")


if __name__ == "__main__":
    logger.warning("🧪 __main__ detectado, ejecutando main()")
    main()
