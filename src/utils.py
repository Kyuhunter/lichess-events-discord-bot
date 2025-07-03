import os
import yaml
import logging
import re  # Added for regex validation
from datetime import datetime, timezone
import asyncio

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

# Custom Discord logging handler
class DiscordHandler(logging.Handler):
    """Handler that emits logs to a Discord channel"""
    def __init__(self, bot, settings, level=logging.INFO):
        super().__init__(level)
        self.bot = bot
        self.settings = settings
        self.pending_logs = []
        self.is_sending = False
        self.formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    
    def emit(self, record):
        # Format the log message
        msg = self.format(record)
        
        # Prefix with emoji based on log level
        if record.levelno >= logging.ERROR:
            msg = f"🔴 {msg}"
        elif record.levelno >= logging.WARNING:
            msg = f"🟠 {msg}"
        elif record.levelno >= logging.INFO:
            msg = f"🔵 {msg}"
        else:
            msg = f"⚪ {msg}"
            
        # Add to queue and process
        self.pending_logs.append(msg)
        self._schedule_processing()
    
    async def _process_logs(self):
        """Process pending logs asynchronously"""
        if self.is_sending or not self.pending_logs:
            return
            
        self.is_sending = True
        try:
            # Group logs to avoid rate limiting
            while self.pending_logs:
                batch = self.pending_logs[:5]
                self.pending_logs = self.pending_logs[5:]
                
                message = "\n".join(batch)
                for guild in self.bot.guilds:
                    gid = str(guild.id)
                    chan_id = self.settings.get(gid, {}).get("notification_channel")
                    if not chan_id:
                        continue
                    
                    channel = guild.get_channel(chan_id)
                    if not channel or not hasattr(channel, "send"):
                        continue
                        
                    try:
                        await channel.send(message)
                    except Exception:
                        # Silently fail - we don't want logging errors to cause more logs
                        pass
                
                # Small delay to avoid rate limits
                if self.pending_logs:
                    await asyncio.sleep(1)
        finally:
            self.is_sending = False
    
    def log_event(self, event_type, message):
        """Log an event notification (create/update/delete)"""
        # Check if event logging is enabled
        discord_conf = _log_conf.get("discord", {})
        if not discord_conf.get("events", True):
            return
            
        if event_type == "create":
            prefix = "✅ "
        elif event_type == "update":
            prefix = "🔄 "
        elif event_type == "delete":
            prefix = "🗑️ "
        else:
            prefix = "ℹ️ "
            
        self.pending_logs.append(f"{prefix}{message}")
        self._schedule_processing()
    
    def _schedule_processing(self):
        """Schedule the processing of logs if conditions are met"""
        if not self.is_sending and self.bot.is_ready():
            asyncio.create_task(self._process_logs())

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
# Discord handler (will be set up in the bot.py)
_discord_handler = None

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

def setup_discord_handler(bot, settings):
    """Set up Discord logging handler."""
    global _discord_handler
    if _discord_handler is not None:
        # Remove existing handler
        logger.removeHandler(_discord_handler)
    
    # Discord handler settings from config
    _discord_conf = _log_conf.get("discord", {})
    discord_level = getattr(logging, _discord_conf.get("level", "INFO").upper(), logging.INFO)
    
    # Create new handler
    _discord_handler = DiscordHandler(bot, settings, level=discord_level)
    _discord_handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    logger.addHandler(_discord_handler)
    return _discord_handler

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

# Security validation functions
def validate_team_slug(slug):
    """
    Validate a team slug against known safe patterns.
    Returns sanitized slug if valid, None if invalid.
    """
    if not isinstance(slug, str):
        return None
        
    # Strip whitespace
    slug = slug.strip()
    
    # Check for valid characters (alphanumeric, hyphens, underscores)
    if not re.match(r'^[a-zA-Z0-9_-]+$', slug):
        return None
        
    # Enforce length limits (adjust as needed for Lichess requirements)
    if not 1 <= len(slug) <= 30:
        return None
        
    return slug

def validate_discord_id(id_value):
    """
    Validate that a value is a valid Discord ID (numeric snowflake).
    Returns the ID as a string if valid, None if invalid.
    """
    if isinstance(id_value, int):
        # Convert to string for consistency
        id_value = str(id_value)
    
    if not isinstance(id_value, str):
        return None
        
    # Check that it's a numeric string
    if not id_value.isdigit():
        return None
        
    # Check reasonable length for Discord IDs
    if not 17 <= len(id_value) <= 20:
        return None
        
    return id_value

def sanitize_message(message):
    """
    Sanitize a message for safe display.
    Preserves some safe markdown but prevents injection attacks.
    """
    if not isinstance(message, str):
        return ""
        
    # Escape backticks to prevent code injection
    sanitized = message.replace('`', '\\`')
    
    # Escape Discord's mention syntax to prevent mentions
    sanitized = sanitized.replace('@', '@\u200B')  # Zero-width space after @
    
    # Escape Discord's URL embedding
    sanitized = re.sub(r'(https?://\S+)', r'<\1>', sanitized)
    
    # Limit to reasonable length
    return sanitized[:1000]  # Limit to 1000 chars
