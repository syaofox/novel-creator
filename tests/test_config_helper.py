import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session
from app.utils.config_helper import get_global_config_dict
from app.models import GlobalConfig


class TestGetGlobalConfigDict:
    @pytest.fixture
    def mock_db(self):
        return MagicMock(spec=Session)

    def test_returns_existing_config(self, mock_db):
        mock_config = MagicMock()
        mock_config.temperature = "0.7"
        mock_config.top_p = "0.9"
        mock_config.max_tokens = 4096
        mock_config.stream = 1
        mock_config.jailbreak_prefix = "test_prefix"
        mock_config.system_template = "test_template"
        mock_config.default_model = "gpt-4"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_config

        result = get_global_config_dict(mock_db)

        assert result["temperature"] == "0.7"
        assert result["top_p"] == "0.9"
        assert result["max_tokens"] == 4096
        assert result["stream"] == 1
        assert result["jailbreak_prefix"] == "test_prefix"
        assert result["system_template"] == "test_template"
        assert result["default_model"] == "gpt-4"

    def test_creates_default_config_when_not_exists(self, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = get_global_config_dict(mock_db)

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

        assert "temperature" in result
        assert "top_p" in result
        assert "max_tokens" in result
        assert "stream" in result
        assert "jailbreak_prefix" in result
        assert "system_template" in result
        assert "default_model" in result
