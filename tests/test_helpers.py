import pytest
from unittest.mock import AsyncMock
from app.utils.helpers import extract_title


class TestExtractTitle:
    def test_chapter_prefix_in_chinese(self):
        result = extract_title("第一章 测试标题\n正文内容")
        assert result == "第一章 测试标题"

    def test_chapter_prefix_with_number(self):
        result = extract_title("第10章 新的开始\n正文")
        assert result == "第10章 新的开始"

    def test_long_first_line_truncated(self):
        result = extract_title("这是一个超过二十个字符的长标题行用来测试截断功能")
        assert len(result) == 23
        assert result.endswith("...")

    def test_short_first_line(self):
        result = extract_title("短标题\n正文")
        assert result == "短标题"

    def test_empty_content(self):
        result = extract_title("")
        assert result == ""

    def test_whitespace_only(self):
        result = extract_title("   \n  ")
        assert result == ""


class TestHandleAIErrors:
    @pytest.mark.asyncio
    async def test_successful_call(self):
        from app.utils.helpers import handle_ai_errors

        async def success():
            return "ok"

        wrapped = handle_ai_errors(success)
        result = await wrapped()
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_timeout_error_returns_504(self):
        from app.utils.helpers import handle_ai_errors

        async def fail():
            raise TimeoutError()

        wrapped = handle_ai_errors(fail)
        result = await wrapped()
        assert result.status_code == 504
        assert "超时" in result.body.decode()

    @pytest.mark.asyncio
    async def test_connection_error_returns_503(self):
        from app.utils.helpers import handle_ai_errors

        async def fail():
            raise ConnectionError("connection failed")

        wrapped = handle_ai_errors(fail)
        result = await wrapped()
        assert result.status_code == 503

    @pytest.mark.asyncio
    async def test_generic_exception_returns_500(self):
        from app.utils.helpers import handle_ai_errors

        async def fail():
            raise ValueError("something went wrong")

        wrapped = handle_ai_errors(fail)
        result = await wrapped()
        assert result.status_code == 500
        assert "something went wrong" in result.body.decode()
