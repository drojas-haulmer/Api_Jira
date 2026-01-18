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
        try:
            data = json.loads(env_json)
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"RUNTIME_CONFIG_JSON no es JSON válido: {env_json}"
            ) from e

        if not isinstance(data, dict):
            raise RuntimeError(
                "RUNTIME_CONFIG_JSON debe ser un JSON objeto (dict), "
                f"pero se recibió: {type(data).__name__}"
            )

        return data

    # ==========================================================
    # 🟢 MODO LOCAL
    # ==========================================================
    local_path = "boards.json"
    if os.path.exists(local_path):
        with open(local_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            raise RuntimeError(
                f"{local_path} debe contener un JSON objeto (dict)"
            )

        return data

    # ==========================================================
    # ❌ ERROR
    # ==========================================================
    raise RuntimeError(
        "No runtime config found. "
        "Provide ENV RUNTIME_CONFIG_JSON or local boards.json"
    )
