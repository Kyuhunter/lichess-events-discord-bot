import os
import logging
from datetime import datetime, timezone

# Ensure data/log directory exists
DATA_DIR = "data"
LOG_DIR = os.path.join(DATA_DIR, "log")
os.makedirs(LOG_DIR, exist_ok=True)

# Root logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Lazy file handler for error logging
typeable = None  # placeholder
_file_handler = None

def ensure_file_handler():
    """Attach a FileHandler for ERROR logs if not already attached."""
    global _file_handler
    if _file_handler is None:
        # Create a daily log file based on UTC date
        log_file = os.path.join(LOG_DIR, f"error_log_{datetime.now(timezone.utc):%Y_%m_%d}.log")
        handler = logging.FileHandler(log_file)
        handler.setLevel(logging.ERROR)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logger.addHandler(handler)
        _file_handler = handler
