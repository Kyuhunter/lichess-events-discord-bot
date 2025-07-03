import pytest
from src.utils import sanitize_message

def test_sanitize_message_basic():
    """Test that basic text is preserved."""
    assert sanitize_message("Hello world") == "Hello world"

def test_sanitize_message_not_string():
    """Test that non-string inputs return empty string."""
    assert sanitize_message(None) == ""
    assert sanitize_message(123) == ""
    assert sanitize_message(["list"]) == ""

def test_sanitize_message_length():
    """Test that long messages are truncated."""
    long_text = "a" * 1500
    assert len(sanitize_message(long_text)) == 1000

def test_sanitize_message_escape_backticks():
    """Test that backticks are escaped."""
    assert sanitize_message("Code: `print('hello')`") == "Code: \\`print('hello')\\`"

def test_sanitize_message_escape_mentions():
    """Test that mentions are escaped."""
    assert "@everyone" not in sanitize_message("@everyone")
    assert "@\u200Beveryone" in sanitize_message("@everyone")

def test_sanitize_message_escape_urls():
    """Test that URLs are safely formatted."""
    assert sanitize_message("Check https://example.com") == "Check <https://example.com>"
