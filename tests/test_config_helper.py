import os
import tempfile

import pytest

from app.repositories.file_repository import FileRepository
from app.utils.config_helper import get_global_config_dict


class TestGetGlobalConfigDict:
    @pytest.fixture
    def repo(self):
        tmpdir = tempfile.mkdtemp()
        data_dir = os.path.join(tmpdir, "data")
        os.makedirs(data_dir)
        return FileRepository(data_dir=data_dir, books_dir=os.path.join(tmpdir, "books"))

    def test_returns_existing_config(self, repo):
        gc = repo.get_global_config()
        gc.temperature = 0.7
        gc.top_p = 0.9
        gc.max_tokens = 4096
        gc.stream = True
        gc.jailbreak_prefix = "test_prefix"
        gc.system_template = "test_template"
        gc.agent_models = {"chapter_writer": "deepseek-v4-pro"}
        repo.save_global_config(gc)

        result = get_global_config_dict(repo)
        assert result["temperature"] == 0.7
        assert result["top_p"] == 0.9
        assert result["max_tokens"] == 4096
        assert result["stream"] is True
        assert result["jailbreak_prefix"] == "test_prefix"
        assert result["system_template"] == "test_template"
        assert result["agent_models"] == {"chapter_writer": "deepseek-v4-pro"}

    def test_creates_default_config_when_not_exists(self, repo):
        result = get_global_config_dict(repo)
        assert "temperature" in result
        assert "top_p" in result
        assert "max_tokens" in result
        assert "stream" in result
        assert "jailbreak_prefix" in result
        assert "system_template" in result
        assert "agent_models" in result
