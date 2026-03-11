import pytest
from unittest.mock import MagicMock
from app.services.ai_service import _extract_json, _get_config_value


class TestExtractJson:
    def test_valid_json(self):
        content = '{"key": "value"}'
        result = _extract_json(content)
        assert result == content

    def test_json_with_extra_whitespace(self):
        content = '  {"key": "value"}  '
        result = _extract_json(content)
        assert result == content

    def test_json_block(self):
        content = """
Some text before
```json
{"key": "value"}
```
Some text after
"""
        result = _extract_json(content)
        assert result == '{"key": "value"}'

    def test_multiple_json_blocks(self):
        content = """
```json
{"invalid": true}
```
```json
{"valid": true}
"""
        result = _extract_json(content)
        assert result == '{"invalid": true}'

    def test_json_in_text(self):
        content = 'Some text {"key": "value"} more text'
        result = _extract_json(content)
        assert result == '{"key": "value"}'

    def test_no_json_returns_original(self):
        content = "No JSON here"
        result = _extract_json(content)
        assert result == "No JSON here"


class TestGetConfigValue:
    def test_book_config_priority(self):
        mock_book = MagicMock()
        mock_book.config = {"temperature": 0.5}
        global_config = {"temperature": 0.7}

        result = _get_config_value(mock_book, global_config, "temperature", 0.8)
        assert result == 0.5

    def test_global_config_fallback(self):
        mock_book = MagicMock()
        mock_book.config = {}
        global_config = {"temperature": 0.7}

        result = _get_config_value(mock_book, global_config, "temperature", 0.8)
        assert result == 0.7

    def test_default_value(self):
        mock_book = MagicMock()
        mock_book.config = {}
        global_config = {}

        result = _get_config_value(mock_book, global_config, "temperature", 0.8)
        assert result == 0.8

    def test_none_book_config(self):
        mock_book = MagicMock()
        mock_book.config = None
        global_config = {"temperature": 0.7}

        result = _get_config_value(mock_book, global_config, "temperature", 0.8)
        assert result == 0.7

    def test_string_to_float(self):
        mock_book = MagicMock()
        mock_book.config = {}
        global_config = {"temperature": "0.9"}

        result = _get_config_value(mock_book, global_config, "temperature", 0.8)
        assert result == 0.9
        assert isinstance(result, float)

    def test_string_to_int(self):
        mock_book = MagicMock()
        mock_book.config = {}
        global_config = {"max_tokens": "4096"}

        result = _get_config_value(mock_book, global_config, "max_tokens", 8192)
        assert result == 4096
        assert isinstance(result, int)

    def test_stream_conversion(self):
        mock_book = MagicMock()
        mock_book.config = {}
        global_config = {"stream": 1}

        result = _get_config_value(mock_book, global_config, "stream", False)
        assert result is True

    def test_stream_zero_returns_false(self):
        mock_book = MagicMock()
        mock_book.config = {}
        global_config = {"stream": 0}

        result = _get_config_value(mock_book, global_config, "stream", True)
        assert result is False
