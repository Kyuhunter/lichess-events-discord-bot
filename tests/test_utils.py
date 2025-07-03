import os
import logging
from pathlib import Path
import pytest

import src.utils as utils

@pytest.fixture(autouse=True)
def temp_log_dir(tmp_path, monkeypatch):
    # Redirect LOG_DIR to temporary directory
    tmp_log = tmp_path / "log"
    tmp_log.mkdir()
    monkeypatch.setattr(utils, "LOG_DIR", str(tmp_log))
    yield tmp_log

def test_ensure_file_handler_creates_file_and_handler(tmp_path, temp_log_dir):
    # Ensure no handler initially
    utils._file_handler = None
    # Call ensure_file_handler
    utils.ensure_file_handler()
    # Handler should be set
    assert utils._file_handler is not None
    # A file should be created in the log directory
    files = list(temp_log_dir.iterdir())
    assert len(files) == 1
    # Filename matches pattern error_log_YYYY_MM_DD.log
    fname = files[0].name
    assert fname.startswith("error_log_") and fname.endswith(".log")

def test_console_handler_level_set_by_config(monkeypatch):
    # Modify config to verbose and console level
    test_conf = {"logging": {"verbose": True, "console": {"level": "DEBUG"}}}
    # Monkeypatch config load
    monkeypatch.setattr(utils, "CONFIG_PATH", __file__)  # point to this file to avoid FileNotFound
    # Manually set utils._conf for test
    utils._conf = test_conf
    # Reload console handler configuration
    # Remove existing console handlers
    for h in list(utils.logger.handlers):
        if isinstance(h, logging.StreamHandler):
            utils.logger.removeHandler(h)
    # Re-run config setup
    utils.reload_console_handler()
    # console handler is added based on updated config
    found = any(isinstance(h, logging.StreamHandler) and h.level == logging.DEBUG for h in utils.logger.handlers)
    assert found
