"""Tests for DeepSeek V4 cache optimization utilities and agent prompt restructuring."""

import pytest
from unittest.mock import MagicMock, AsyncMock

from app.utils.ai_utils import extract_stable_sections, extract_dynamic_sections
from app.utils.ai_utils import MEMORY_STABLE_SECTIONS, MEMORY_DYNAMIC_SECTIONS, PROMPT_DEFAULTS
from app.services.agents.chapter_writer_agent import ChapterWriterAgent
from app.services.agents.summary_agent import SummaryAgent


SAMPLE_MEMORY_SUMMARY = """【人物卡】
张三: 主角,25岁,勇敢善良
李四: 配角,30岁,智慧沉稳

【世界观】
仙侠世界,修炼等级:炼气-筑基-金丹

【风格规范】
第三人称,语言优美,节奏适中

【主线进度】
第1章: 下山历练 - 主角离开师门,踏上旅程（已完成）
第2章: 遭遇强敌 - 主角遇到第一个对手（待写）

【伏笔清单】
- 神秘玉佩的秘密（待回收）
- 师门背叛的真相（待回收）

【其他信息】
第1章引入了关键道具"神秘玉佩"
"""


class TestExtractStableSections:
    def test_returns_characters_worldview_style(self):
        result = extract_stable_sections(SAMPLE_MEMORY_SUMMARY)
        assert "【人物卡】" in result
        assert "张三" in result
        assert "【世界观】" in result
        assert "仙侠世界" in result
        assert "【风格规范】" in result
        assert "第三人称" in result

    def test_does_not_contain_dynamic_sections(self):
        result = extract_stable_sections(SAMPLE_MEMORY_SUMMARY)
        assert "【主线进度】" not in result
        assert "【伏笔清单】" not in result
        assert "【其他信息】" not in result

    def test_empty_input(self):
        assert extract_stable_sections("") == ""
        assert extract_stable_sections(None) == ""

    def test_partial_sections(self):
        summary = """【人物卡】
张三: 主角
【主线进度】
第1章: 开始（已完成）
"""
        result = extract_stable_sections(summary)
        assert "【人物卡】" in result
        assert "张三" in result
        assert "【世界观】" not in result
        assert "【风格规范】" not in result

    def test_all_sections_present(self):
        sections_found = []
        result = extract_stable_sections(SAMPLE_MEMORY_SUMMARY)
        for key in MEMORY_STABLE_SECTIONS:
            if f"【{key}】" in result:
                sections_found.append(key)
        assert sections_found == MEMORY_STABLE_SECTIONS


class TestExtractDynamicSections:
    def test_returns_progress_foreshadowing_other(self):
        result = extract_dynamic_sections(SAMPLE_MEMORY_SUMMARY)
        assert "【主线进度】" in result
        assert "下山历练" in result
        assert "【伏笔清单】" in result
        assert "神秘玉佩" in result
        assert "【其他信息】" in result

    def test_does_not_contain_stable_sections(self):
        result = extract_dynamic_sections(SAMPLE_MEMORY_SUMMARY)
        assert "【人物卡】" not in result
        assert "【世界观】" not in result
        assert "【风格规范】" not in result

    def test_empty_input(self):
        assert extract_dynamic_sections("") == ""
        assert extract_dynamic_sections(None) == ""

    def test_all_sections_present(self):
        sections_found = []
        result = extract_dynamic_sections(SAMPLE_MEMORY_SUMMARY)
        for key in MEMORY_DYNAMIC_SECTIONS:
            if f"【{key}】" in result:
                sections_found.append(key)
        assert sections_found == MEMORY_DYNAMIC_SECTIONS


class TestChapterWriterAgentCacheOptimization:
    @pytest.fixture
    def mock_book(self):
        book = MagicMock()
        book.style = "语言优美流畅，叙事自然"
        book.memory_summary = SAMPLE_MEMORY_SUMMARY
        book.config = {"temperature": 0.78, "top_p": 0.92, "max_tokens": 16384, "system_template": "你是我的长篇小说专属写手。请严格遵守以下写作风格规范：\n{style}"}
        return book

    @pytest.fixture
    def agent(self, mock_book):
        ai_service = MagicMock()
        ai_service.global_config = {}
        return ChapterWriterAgent(ai_service, mock_book, {})

    def test_system_prompt_includes_stable_sections(self, agent):
        prompt = agent.system_prompt
        assert "【人物卡】" in prompt
        assert "张三" in prompt
        assert "【世界观】" in prompt
        assert "仙侠世界" in prompt
        assert "【风格规范】" in prompt
        assert "第三人称" in prompt  # 风格规范是 stable section, 应在 system prompt 中

    def test_system_prompt_excludes_dynamic_sections(self, agent):
        prompt = agent.system_prompt
        assert "【主线进度】" not in prompt
        assert "【伏笔清单】" not in prompt

    def test_user_prompt_includes_dynamic_sections(self, agent):
        user_content = agent._build_user_content(3, "主角遇到强敌", "上一章结尾...")
        assert "【主线进度】" in user_content
        assert "【伏笔清单】" in user_content
        assert "【其他信息】" in user_content

    def test_user_prompt_excludes_stable_sections(self, agent):
        user_content = agent._build_user_content(3, "主角遇到强敌", "上一章结尾...")
        assert "【人物卡】" not in user_content
        assert "【世界观】" not in user_content
        assert "【风格规范】" not in user_content

    def test_user_prompt_contains_chapter_info(self, agent):
        user_content = agent._build_user_content(3, "核心事件", "上一章结尾")
        assert "第3章正文" in user_content
        assert "核心事件" in user_content
        assert "上一章结尾" in user_content

    def test_messages_structure(self, agent):
        messages = agent._build_messages(3, "核心事件", "上一章结尾")
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert "【人物卡】" in messages[0]["content"]  # stable in system
        assert "【主线进度】" in messages[1]["content"]  # dynamic in user

    @pytest.mark.asyncio
    async def test_write_calls_with_messages(self, agent):
        ai_service = agent.ai_service
        ai_service.call_with_messages = AsyncMock(return_value="第3章正文内容...")

        result = await agent.write(3, "核心事件", "上一章结尾")
        assert result == "第3章正文内容..."

        call_kwargs = ai_service.call_with_messages.call_args[1]
        assert call_kwargs["messages"][0]["role"] == "system"
        assert call_kwargs["messages"][1]["role"] == "user"

    def test_system_prompt_stability_for_cache(self, agent):
        """验证多次调用 system_prompt 保持一致"""
        prompt1 = agent.system_prompt
        prompt2 = agent.system_prompt
        assert prompt1 == prompt2

    def test_different_chapters_same_system_prompt(self, agent):
        """验证不同章节的 system prompt 相同(关键缓存优化点)"""
        messages1 = agent._build_messages(3, "事件A", "结尾A")
        messages2 = agent._build_messages(4, "事件B", "结尾B")
        assert messages1[0]["content"] == messages2[0]["content"]  # system prompt identical

    def test_system_prompt_without_memory(self):
        """验证无 memory_summary 时正常工作"""
        book = MagicMock()
        book.style = "简洁干练"
        book.memory_summary = ""
        book.config = {"system_template": "你是我的长篇小说专属写手。请严格遵守以下写作风格规范：\n{style}"}

        ai_service = MagicMock()
        ai_service.global_config = {}
        agent = ChapterWriterAgent(ai_service, book, {})

        prompt = agent.system_prompt
        assert "人物卡" not in prompt
        assert "简洁干练" in prompt


SAMPLE_OLD_SUMMARY = """【人物卡】
张三: 主角,25岁,勇敢善良
李四: 配角,30岁,智慧沉稳

【世界观】
仙侠世界,修炼等级:炼气-筑基-金丹

【风格规范】
第三人称,语言优美,节奏适中

【主线进度】
第1章: 下山历练 - 主角离开师门,踏上旅程（已完成）

【伏笔清单】
- 神秘玉佩的秘密（待回收）

【其他信息】
第1章引入了关键道具"神秘玉佩"
"""


class TestSummaryAgentCacheOptimization:
    @pytest.fixture
    def mock_book(self):
        book = MagicMock()
        book.memory_summary = SAMPLE_OLD_SUMMARY
        book.config = {}
        return book

    @pytest.fixture
    def agent(self, mock_book):
        ai_service = MagicMock()
        ai_service.global_config = {}
        return SummaryAgent(ai_service, mock_book, {})

    def test_system_prompt_contains_format_instructions(self, agent):
        prompt = agent.system_prompt
        assert "【人物卡】" in prompt
        assert "【世界观】" in prompt
        assert "【风格规范】" in prompt
        assert "【主线进度】" in prompt
        assert "【伏笔清单】" in prompt
        assert "【其他信息】" in prompt

    def test_system_prompt_is_long_for_cache(self, agent):
        prompt = agent.system_prompt
        assert len(prompt) > 400, "system prompt should be long enough for meaningful prefix caching"

    def test_user_prompt_contains_dynamic_data_only(self, agent):
        user = agent.build_prompt(
            new_chapter="主角击败了第一个敌人",
            chapter_number=2,
            chapter_title="初遇强敌",
            next_chapter=3,
            is_last_chapter=False,
        )
        assert "旧摘要如下" in user or "现有旧摘要如下" in user or "旧摘要：" in user
        assert "张三" in user
        assert "主角击败了第一个敌人" in user
        assert "初遇强敌" in user

    def test_user_prompt_excludes_format_instructions(self, agent):
        user = agent.build_prompt(
            new_chapter="内容",
            chapter_number=2,
            chapter_title="标题",
            next_chapter=3,
            is_last_chapter=False,
        )
        assert "更新规则" not in user
        assert "请确保伏笔回收信息清晰" not in user

    def test_different_chapters_same_system_prompt(self, agent):
        messages1 = agent._build_messages("内容A", 2, False, "标题A")
        messages2 = agent._build_messages("内容B", 3, False, "标题B")
        assert messages1[0]["content"] == messages2[0]["content"]

    def test_system_prompt_stability_for_cache(self, agent):
        prompt1 = agent.system_prompt
        prompt2 = agent.system_prompt
        assert prompt1 == prompt2

    def test_messages_structure(self, agent):
        messages = agent._build_messages("新章节内容", 2, False, "第2章")
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert len(messages[0]["content"]) > 400
        assert "主线进度" in messages[0]["content"]

    def test_system_prompt_identical_across_books(self):
        ai_service = MagicMock()
        ai_service.global_config = {}
        book1 = MagicMock()
        book1.memory_summary = SAMPLE_OLD_SUMMARY
        book1.config = {}
        book2 = MagicMock()
        book2.memory_summary = SAMPLE_OLD_SUMMARY
        book2.config = {}

        agent1 = SummaryAgent(ai_service, book1, {})
        agent2 = SummaryAgent(ai_service, book2, {})
        assert agent1.system_prompt == agent2.system_prompt

    def test_user_prompt_last_chapter_no_next_chapter_placeholder(self, agent):
        user = agent.build_prompt(
            new_chapter="最终决战",
            chapter_number=10,
            chapter_title="终章",
            next_chapter=11,
            is_last_chapter=True,
        )
        assert "最后一章" in user or "最后" in user

    @pytest.mark.asyncio
    async def test_update_calls_with_messages(self, agent):
        ai_service = agent.ai_service
        ai_service.call_with_messages = AsyncMock(return_value="更新后的摘要...")

        result = await agent.update(
            new_chapter_text="主角击败了敌人",
            chapter_number=2,
            is_last_chapter=False,
            chapter_title="初遇强敌",
        )
        assert result == "更新后的摘要..."

        call_kwargs = ai_service.call_with_messages.call_args[1]
        assert call_kwargs["messages"][0]["role"] == "system"
        assert call_kwargs["messages"][1]["role"] == "user"
