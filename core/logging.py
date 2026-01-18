# core/logging.py
import logging
import os


LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

HUMAN_FORMAT = (
    "%(asctime)s | %(levelname)-5s | %(name)s:%(funcName)s:%(lineno)d\n"
    "  %(message)s"
)


def is_cloud_run() -> bool:
    """
    Detecta Cloud Run / GKE real.
    NO Compute Engine.
    """
    return bool(os.getenv("K_SERVICE"))


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(LOG_LEVEL)
    logger.propagate = False

    # ==================================================
    # ☁️ Cloud Run / GKE → logging estructurado
    # ==================================================
    if is_cloud_run():
        try:
            from google.cloud.logging.handlers import StructuredLogHandler

            handler = StructuredLogHandler()
            handler.setLevel(LOG_LEVEL)
            logger.addHandler(handler)

            logger.info("Cloud Logging estructurado habilitado")
            return logger

        except Exception:
            # fallback seguro
            pass

    # ==================================================
    # 🖥️ LOCAL o COMPUTE ENGINE → stdout limpio
    # ==================================================
    handler = logging.StreamHandler()
    handler.setLevel(LOG_LEVEL)

    formatter = logging.Formatter(
        HUMAN_FORMAT,
        datefmt="%H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    logger.info("Logging estándar habilitado")
    return logger
