# config/runtime.py
print(">>> config/runtime.py LOADED")

import json
import os
from typing import Dict, Any


def load_runtime_config() -> Dict[str, Any]:
    """
    Carga configuración de ejecución.

    Prioridad:
    1) ENV RUNTIME_CONFIG_JSON  → Cloud Run / Workflows
    2) Archivo local boards.json → Ejecución local
    """

    # ==========================================================
    # ☁️ MODO GCP (Workflow / Cloud Run)
    # ==========================================================
    env_json = os.getenv("RUNTIME_CONFIG_JSON")
    if env_json:
        return json.loads(env_json)

    # ==========================================================
    # 🟢 MODO LOCAL
    # ==========================================================
    local_path = "boards.json"
    if os.path.exists(local_path):
        with open(local_path, "r", encoding="utf-8") as f:
            return json.load(f)

    raise RuntimeError(
        "No runtime config found. "
        "Provide ENV RUNTIME_CONFIG_JSON or local boards.json"
    )
