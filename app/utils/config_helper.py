from sqlalchemy.orm import Session

from app.models import GlobalConfig
from app.constants import (
    DEFAULT_TEMPERATURE,
    DEFAULT_TOP_P,
    DEFAULT_MAX_TOKENS,
    DEFAULT_STREAM,
    DEFAULT_JAILBREAK_PREFIX,
    DEFAULT_SYSTEM_TEMPLATE,
    DEFAULT_MODEL,
)


def get_global_config_dict(db: Session) -> dict:
    """获取全局配置字典

    如果数据库中不存在配置，则创建默认配置记录。

    Args:
        db: 数据库会话

    Returns:
        包含所有配置字段的字典
    """
    config = db.query(GlobalConfig).filter(GlobalConfig.id == 1).first()

    if not config:
        config = GlobalConfig(
            id=1,
            temperature=DEFAULT_TEMPERATURE,
            top_p=DEFAULT_TOP_P,
            max_tokens=DEFAULT_MAX_TOKENS,
            stream=DEFAULT_STREAM,
            jailbreak_prefix=DEFAULT_JAILBREAK_PREFIX,
            system_template=DEFAULT_SYSTEM_TEMPLATE,
            default_model=DEFAULT_MODEL,
        )
        db.add(config)
        db.commit()
        db.refresh(config)

    return {
        "deepseek_api_key": config.deepseek_api_key or "",
        "deepseek_base_url": config.deepseek_base_url or "",
        "temperature": config.temperature,
        "top_p": config.top_p,
        "max_tokens": config.max_tokens,
        "stream": config.stream,
        "jailbreak_prefix": config.jailbreak_prefix or "",
        "system_template": config.system_template or "",
        "default_model": config.default_model or "",
    }
