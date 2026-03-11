# 初始化提示模板
INIT_PROMPT = """你是一个小说创作辅助AI。请根据用户提供的创意，生成小说的基础设定，并以JSON格式返回。
用户创意：{basic_idea}
小说类型：{genre}
目标章节数：{target_chapters}

请严格按照以下JSON结构输出，outline数组必须包含恰好{target_chapters}个章节：

{{
  "characters": [
    {{
      "name": "角色姓名",
      "nickname": "昵称",
      "age": 年龄,
      "appearance": "外貌描述",
      "personality": "性格特点",
      "background": "背景故事",
      "goal": "角色目标",
      "relationships": "人物关系"
    }}
  ],
  "world_view": {{
    "setting": "世界观设定",
    "special_rules": "特殊规则",
    "themes": "主题"
  }},
  "style": {{
    "narrative_perspective": "叙事视角",
    "language_style": "语言风格",
    "pace": "节奏特点",
    "target_audience": "目标读者"
  }},
  "outline": [
    {{
      "chapter": 1,
      "title": "章节标题",
      "core_event": "本章核心事件"
    }}
  ],
  "foreshadowing": ["伏笔1", "伏笔2"],
  "other": {{
    "novel_title": "小说标题",
    "key_points": "关键要点",
    "writing_guidance": "写作指导"
  }}
}}

请确保：
1. outline数组必须有{target_chapters}个章节对象，chapter从1开始连续编号
2. 输出是有效的JSON格式，不要包含其他说明文字"""

# 写章节提示模板
WRITE_CHAPTER_PROMPT = """请根据以下信息创作第{chapter_number}章正文。
本章核心事件：{core_event}
上一章结尾：{prev_ending}
请写出完整的一章，注意承上启下，保持风格一致。"""

# 更新摘要提示模板
UPDATE_SUMMARY_PROMPT = """你是一个小说摘要更新专家。现有旧摘要如下：
{old_summary}

新写成的章节全文如下（第{chapter_number}章）：
{new_chapter}

请根据新章节的内容更新摘要，必须保持六部分格式。重点注意：
1. 【主线进度】：必须更新到第{chapter_number}章，清晰列出已完成章节和后续章节的计划
2. 【伏笔清单】：检查本章是否回收了旧伏笔，如有回收则标记"已回收"；如有新伏笔则添加到列表中；分析本章是否为后续伏笔埋下铺垫
3. 【人物卡】：如有新人物出场或人物关系变化，必须更新
4. 【其他信息】：记录本章的关键情节点和重要发展

格式要求：
【人物卡】
更新后的内容
【世界观】
更新后的内容
【风格规范】
更新后的内容
【主线进度】
第1章: ...（已完成）
第2章: ...（已完成）
...
第{chapter_number}章: 本章核心事件（已完成）
第{next_chapter}章: 计划中的事件
...
【伏笔清单】
- 伏笔1（已回收✓）
- 伏笔2（本章回收✓）
- 伏笔3（待回收）
- 新伏笔: ...
【其他信息】
更新后的内容

请确保伏笔回收信息清晰，不要遗漏任何伏笔。直接输出更新后的摘要，不要包含其他说明。"""

# 压缩摘要提示模板
COMPRESS_SUMMARY_PROMPT = """请将以下小说摘要压缩至2500字以内，保留六部分格式：
【人物卡】
【世界观】
【风格规范】
【主线进度】
【伏笔清单】
【其他信息】

原摘要：
{summary}

直接输出压缩后的摘要。"""
