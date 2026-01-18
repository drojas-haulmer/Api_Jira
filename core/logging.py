# core/logging.py
import logging
import os


LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()


HUMAN_FORMAT = (
    "%(asctime)s | %(levelname)-5s | %(name)s:%(funcName)s:%(lineno)d\n"
    "  %(message)s"
)


def is_gcp_environment() -> bool:
    return bool(
        os.getenv("K_SERVICE")  # Cloud Run
        or os.getenv("GOOGLE_CLOUD_PROJECT")
    )


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(LOG_LEVEL)
    logger.propagate = False

    if is_gcp_environment():
        # ---------- GCP (JSON estructurado) ----------
        try:
            from google.cloud.logging.handlers import StructuredLogHandler

            handler = StructuredLogHandler()
            handler.setLevel(LOG_LEVEL)
            logger.addHandler(handler)

            logger.info("Cloud Logging habilitado", extra={"env": "gcp"})
            return logger

        except Exception as e:
            # fallback a local si algo raro pasa
            pass

    # ---------- LOCAL (humano y ordenado) ----------
    handler = logging.StreamHandler()
    handler.setLevel(LOG_LEVEL)

    formatter = logging.Formatter(
        HUMAN_FORMAT,
        datefmt="%H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    logger.info("Logging local habilitado", extra={"env": "local"})
    return logger
