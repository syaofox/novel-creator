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


def get_global_config_dict(db: Session) -> dict[str, str | int]:
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
            temperature=str(DEFAULT_TEMPERATURE),
            top_p=str(DEFAULT_TOP_P),
            max_tokens=DEFAULT_MAX_TOKENS,
            stream=1 if DEFAULT_STREAM else 0,
            jailbreak_prefix=DEFAULT_JAILBREAK_PREFIX,
            system_template=DEFAULT_SYSTEM_TEMPLATE,
            default_model=DEFAULT_MODEL,
        )
        db.add(config)
        db.commit()
        db.refresh(config)

    return {
        "temperature": config.temperature,
        "top_p": config.top_p,
        "max_tokens": config.max_tokens,
        "stream": config.stream,
        "jailbreak_prefix": config.jailbreak_prefix,
        "system_template": config.system_template,
        "default_model": config.default_model,
    }
