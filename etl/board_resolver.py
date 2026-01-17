# etl/board_resolver.py
print(">>> etl/board_resolver.py LOADED")

from typing import List, Dict, Optional


def resolve_boards(
    *,
    jira,
    jira_project_key: str,
    runtime_boards: Optional[List[Dict]] = None,
) -> List[Dict]:
    """
    Resuelve el alcance FINAL de la ejecución.

    Reglas DEFINITIVAS:

    1) runtime_boards con elementos:
        → ejecutar SOLO esos boards
        → cada uno debe traer:
            { board_id, target_table }

    2) runtime_boards NO existe o es []:
        → ejecutar a NIVEL DE PROYECTO
        → NO se descubren boards
        → una sola entrada lógica

    Retorna siempre una lista homogénea de dicts.
    """

    # ==========================================================
    # 🟢 CASO 1: BOARDS EXPLÍCITOS
    # ==========================================================
    if runtime_boards and len(runtime_boards) > 0:
        jira.logger.info(
            "🔍 [board_resolver] boards explícitos especificados: %s",
            runtime_boards,
        )

        resolved = []

        for b in runtime_boards:
            if "board_id" not in b:
                raise ValueError(f"runtime board inválido (falta board_id): {b}")

            if "target_table" not in b:
                raise ValueError(f"runtime board inválido (falta target_table): {b}")

            resolved.append(
                {
                    "scope": "BOARD",
                    "jira_project_key": jira_project_key,
                    "board_id": int(b["board_id"]),
                    "target_table": str(b["target_table"]),
                }
            )

        return resolved

    # ==========================================================
    # 🟢 CASO 2: PROYECTO COMPLETO
    # ==========================================================
    jira.logger.info(
        "🔍 [board_resolver] boards NO especificados o vacíos → ejecución a nivel de PROYECTO (%s)",
        jira_project_key,
    )

    return [
        {
            "scope": "PROJECT",
            "jira_project_key": jira_project_key,
            "board_id": None,
            "target_table": f"{jira_project_key}_project_raw",
        }
    ]
