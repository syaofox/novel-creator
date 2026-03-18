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

请根据新章节的内容更新摘要,用来指导后续章节撰写，必须保持六部分格式。所有部分中涉及当前章节的叙述，都必须用"第{chapter_number}章"来指代，禁止使用"本章"、"这一章"等模糊表述。重点注意：
1. 【主线进度】：必须更新到第{chapter_number}章，清晰列出已完成章节和后续章节的计划
2. 【伏笔清单】：检查本章是否回收了旧伏笔，如有回收则标记"第{chapter_number}章已回收"；如有新伏笔则添加到列表中；分析本章是否为后续伏笔埋下铺垫
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
第{chapter_number}章: 第{chapter_number}章核心事件（已完成）
第{next_chapter}章: 计划中的事件
...
【伏笔清单】
- 伏笔1（第x章已回收✓）
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

# 初始化书籍 system prompt
INIT_BOOK_SYSTEM_PROMPT = """你是一个专业的小说创作辅助AI。请严格按照以下格式输出，每个字段用【】标记包裹，中间是有效的JSON。

重要规则：
1. 只输出以下6个字段，顺序必须为：characters、world_view、style、outline、foreshadowing、other
2. 每个字段格式为：【字段名】<JSON内容>【字段名】，标记必须成对出现
3. JSON内容必须是有效的JSON，符合下方给出的结构
4. 不要添加任何额外文本、说明、解释或注释
5. 不要修改字段名，不要省略任何字段
6. outline数组必须包含恰好{target_chapters}个章节对象，chapter从1开始连续编号

符号使用规则（必须严格遵守）：
1. JSON语法符号（必须使用英文半角）：
   - 所有键名必须用英文双引号（"key"）
   - 所有字符串值必须用英文双引号括起来（"value"）
   - 所有冒号（:）、逗号（,）、方括号（[]）、花括号（{{}}）必须使用英文半角
   - 禁止使用中文引号作为JSON语法符号

2. 字符串内容符号（必须使用中文全角）：
   - 字符串值内部的标点符号必须使用中文全角符号
   - 包括：逗号（，）、句号（。）、冒号（：）、分号（；）、感叹号（！）、问号（？）
   - 示例：正确→"外貌描述，性格特点。" 错误→"外貌描述,性格特点."

3. 验证要求：
   - 输出前请检查JSON语法有效性
   - 确保所有英文引号正确闭合
   - 确保没有尾随逗号

字段格式示例（注意符号使用）：

【characters】
[
  {{
    "name": "张三",
    "age": 25,
    "appearance": "黑色短发，身高180cm。",
    "personality": "性格内向，但做事认真负责；"
  }}
]
【characters】

【world_view】
{{
  "setting": "现代都市背景，存在超能力者。",
  "themes": "成长与选择，友情与背叛。"
}}
【world_view】

请严格按照以下结构输出：

【characters】
[
  {{
    "name": "角色姓名",
    "nickname": "昵称",
    "age": 20,
    "appearance": "外貌描述",
    "personality": "性格特点",
    "background": "背景故事",
    "goal": "角色目标",
    "relationships": "人物关系"
  }}
]
【characters】

【world_view】
{{
  "setting": "世界观设定",
  "special_rules": "特殊规则",
  "themes": "主题"
}}
【world_view】

【style】
{{
  "narrative_perspective": "叙事视角",
  "language_style": "语言风格",
  "pace": "节奏特点",
  "target_audience": "目标读者"
}}
【style】

【outline】
[
  {{"chapter": 1, "title": "章节标题", "core_event": "本章核心事件"}}
]
【outline】

【foreshadowing】
["伏笔1", "伏笔2"]
【foreshadowing】

【other】
{{
  "novel_title": "小说标题",
  "key_points": "关键要点",
  "writing_guidance": "写作指导"
}}
【other】

重要：JSON 必须是有效的 JSON 语法。确保：
1. 所有字符串值必须用英文双引号括起来（例如："value"），不要使用单引号或省略引号
2. 对象键必须用英文双引号括起来
3. 不要有尾随逗号
4. 字符串内容请使用中文全角标点符号（，。；：！？等）
5. 禁止在JSON语法中使用中文引号
{style_section}"""

# 更新摘要 system prompt
UPDATE_SUMMARY_SYSTEM_PROMPT = (
    "你是一个小说摘要更新专家，请根据旧摘要和新章节生成更新后的摘要，保持6部分格式。重点关注伏笔回收和主线进度更新。"
)

# 压缩摘要 system prompt
COMPRESS_SUMMARY_SYSTEM_PROMPT = "你是一个摘要压缩专家，请将以下小说摘要压缩至2500字以内，保留6部分格式。"
