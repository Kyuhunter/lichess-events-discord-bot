import os
import yaml
import logging
from datetime import datetime, timezone

# Ensure data/log directory exists
DATA_DIR = "data"
LOG_DIR = os.path.join(DATA_DIR, "log")
os.makedirs(LOG_DIR, exist_ok=True)

# Load logging config
CONFIG_PATH = os.path.join(os.getcwd(), "config", "config.yaml")
try:
    with open(CONFIG_PATH) as f:
        _conf = yaml.safe_load(f) or {}
except FileNotFoundError:
    _conf = {}
_log_conf = _conf.get("logging", {})
# Determine global log level
_level_name = _log_conf.get("level", "INFO").upper()
_global_level = getattr(logging, _level_name, logging.INFO)
if _log_conf.get("verbose", False):
    _global_level = logging.DEBUG
# Configure root logger
logger = logging.getLogger()
logger.setLevel(_global_level)
# Console handler
_console_conf = _log_conf.get("console", {})
_console_level = getattr(logging, _console_conf.get("level", "INFO").upper(), _global_level)
_ch = logging.StreamHandler()
_ch.setLevel(_console_level)
_ch.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
logger.addHandler(_ch)

# Lazy file handler for error logging
typeable = None  # placeholder
_file_handler = None

def ensure_file_handler():
    """Attach a FileHandler for ERROR logs if not already attached."""
    global _file_handler
    if _file_handler is None:
        # File handler settings from config
        _file_conf = _log_conf.get("file", {})
        filename_pattern = _file_conf.get("filename_pattern", "error_log_%Y_%m_%d.log")
        file_level = getattr(logging, _file_conf.get("level", "ERROR").upper(), logging.ERROR)
        # Create log file based on UTC date and pattern
        log_filename = datetime.now(timezone.utc).strftime(filename_pattern)
        log_file = os.path.join(LOG_DIR, log_filename)
        handler = logging.FileHandler(log_file)
        handler.setLevel(file_level)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logger.addHandler(handler)
        _file_handler = handler
