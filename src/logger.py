import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOG_PATH = Path("logs/app.log")
_LOG_PATH.parent.mkdir(exist_ok=True)

logger = logging.getLogger("second_brain")
logger.setLevel(logging.DEBUG)

if not logger.handlers:
    file_handler = RotatingFileHandler(_LOG_PATH, maxBytes=1_000_000, backupCount=3)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s"))

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(logging.Formatter("%(levelname)s | %(message)s"))

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
