from app.repositories.file_repository import FileRepository


def get_global_config_dict(repo: FileRepository) -> dict:
    """获取全局配置字典"""
    config = repo.get_global_config()
    return {
        "deepseek_api_key": config.deepseek_api_key or "",
        "deepseek_base_url": config.deepseek_base_url or "",
        "temperature": config.temperature,
        "top_p": config.top_p,
        "max_tokens": config.max_tokens,
        "stream": config.stream,
        "jailbreak_prefix": config.jailbreak_prefix or "",
        "system_template": config.system_template or "",
        "agent_models": config.agent_models,
        "agent_prompts": config.agent_prompts,
    }
