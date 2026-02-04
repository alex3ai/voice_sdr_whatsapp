import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler

def setup_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    if logger.hasHandlers():
        return logger

    # Formato dos logs
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(filename)s:%(lineno)d | %(message)s",
        datefmt="%H:%M:%S"
    )

    # 1. Handler do Console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 2. Handler de Arquivo (Blindado)
    log_file_path = None
    try:
        # Tenta /tmp primeiro para evitar problemas de permissão no Docker
        temp_logs = Path("/tmp/voice_sdr_logs")
        temp_logs.mkdir(mode=0o777, parents=True, exist_ok=True)
        log_file_path = temp_logs / "voice_sdr.log"
    except Exception:
        pass # Falha silenciosa, usa só console

    if log_file_path:
        try:
            file_handler = RotatingFileHandler(
                log_file_path, maxBytes=5*1024*1024, backupCount=3, encoding="utf-8"
            )
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception:
            pass

    return logger
