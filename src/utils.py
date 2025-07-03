import os
import yaml
import logging
from datetime import datetime, timezone

# Auto-reloading handler list to support dynamic console handler based on config
class HandlerList(list):
    """Custom handler list that reloads console handler if missing."""
    def __iter__(self):
        # If no StreamHandler present, reload console handler
        if not any(isinstance(h, logging.StreamHandler) for h in super().__iter__()):
            reload_console_handler()
        return super().__iter__()
    def __getitem__(self, index):
        if not any(isinstance(h, logging.StreamHandler) for h in super().__iter__()):
            reload_console_handler()
        return super().__getitem__(index)
    def __len__(self):
        if not any(isinstance(h, logging.StreamHandler) for h in super().__iter__()):
            reload_console_handler()
        return super().__len__()

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
# Wrap handlers list to auto-reload console handler
logger.handlers = HandlerList(logger.handlers)

# Lazy file handler for error logging
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

def reload_console_handler():
    """Reconfigure console handler based on _log_conf."""
    import logging as _logging_module
    global logger, _log_conf, _global_level
    # Reload log configuration from updated _conf
    _log_conf = _conf.get("logging", {})
    # Determine global level
    level_name = _log_conf.get("level", "INFO").upper()
    _global_level = getattr(_logging_module, level_name, _global_level)
    if _log_conf.get("verbose", False):
        _global_level = _logging_module.DEBUG
    logger.setLevel(_global_level)
    # Configure console handler
    _console_conf = _log_conf.get("console", {})
    console_level_name = _console_conf.get("level", level_name).upper()
    _console_level = getattr(_logging_module, console_level_name, _global_level)
    ch = _logging_module.StreamHandler()
    ch.setLevel(_console_level)
    ch.setFormatter(_logging_module.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(ch)
