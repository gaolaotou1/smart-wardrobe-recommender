import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AgentConfig:
    chat_v2_enabled: bool
    recommendation_v2_enabled: bool
    text_model_provider: str
    agent_model: str
    fast_model: str
    max_replans: int
    max_tool_calls: int
    run_timeout_seconds: int
    memory_gate_interval_turns: int
    outfit_mutations_enabled: bool
    long_term_memory_enabled: bool
    image_analysis_enabled: bool
    weather_enabled: bool
    semantic_recall_enabled: bool
    advanced_readonly_sql_enabled: bool
    checkpoint_path: str
    deepseek_api_key: str
    deepseek_base_url: str
    ark_api_token: str
    ark_base_url: str
    ark_model: str
    jwt_secret: str

    def validate_runtime(self) -> list[str]:
        errors = []
        if self.text_model_provider not in {"deepseek", "ark"}:
            errors.append("TEXT_MODEL_PROVIDER 必须是 deepseek 或 ark")
        if self.text_model_provider == "deepseek" and not self.deepseek_api_key:
            errors.append("DEEPSEEK_API_KEY 未配置")
        if self.text_model_provider == "ark" and not self.ark_api_token:
            errors.append("ARK_API_TOKEN 未配置")
        if self.image_analysis_enabled and not self.ark_api_token:
            errors.append("图片分析已启用，但 ARK_API_TOKEN 未配置")
        if not self.agent_model or not self.fast_model:
            errors.append("文本模型名不得为空")
        if not 1 <= self.max_replans <= 2:
            errors.append("AGENT_MAX_REPLANS 必须在 1–2 之间")
        if not 1 <= self.max_tool_calls <= 8:
            errors.append("AGENT_MAX_TOOL_CALLS 必须在 1–8 之间")
        if not 10 <= self.run_timeout_seconds <= 90:
            errors.append("AGENT_RUN_TIMEOUT_SECONDS 必须在 10–90 之间")
        if len(self.jwt_secret) < 32 or self.jwt_secret.startswith("replace_"):
            errors.append("JWT_SECRET 必须配置为至少 32 字符的随机值")
        return errors

    def ensure_checkpoint_dir(self) -> Path:
        path = Path(self.checkpoint_path).expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        return path


def load_agent_config():
    return AgentConfig(
        chat_v2_enabled=get_bool_env("CHAT_V2_ENABLED", True),
        recommendation_v2_enabled=get_bool_env("RECOMMENDATION_V2_ENABLED", True),
        text_model_provider=os.environ.get("TEXT_MODEL_PROVIDER", "deepseek"),
        agent_model=os.environ.get("AGENT_MODEL", "deepseek-v4-flash"),
        fast_model=os.environ.get("FAST_MODEL", "deepseek-v4-flash"),
        max_replans=int(os.environ.get("AGENT_MAX_REPLANS", "2")),
        max_tool_calls=int(os.environ.get("AGENT_MAX_TOOL_CALLS", "8")),
        run_timeout_seconds=int(os.environ.get("AGENT_RUN_TIMEOUT_SECONDS", "90")),
        memory_gate_interval_turns=int(os.environ.get("MEMORY_GATE_INTERVAL_TURNS", "10")),
        outfit_mutations_enabled=get_bool_env("OUTFIT_MUTATIONS_ENABLED", True),
        long_term_memory_enabled=get_bool_env("LONG_TERM_MEMORY_ENABLED", True),
        image_analysis_enabled=get_bool_env("IMAGE_ANALYSIS_ENABLED", True),
        weather_enabled=get_bool_env("WEATHER_ENABLED", False),
        semantic_recall_enabled=get_bool_env("SEMANTIC_RECALL_ENABLED", False),
        advanced_readonly_sql_enabled=get_bool_env("ADVANCED_READONLY_SQL_ENABLED", False),
        checkpoint_path=os.environ.get("AGENT_CHECKPOINT_PATH", "./data/langgraph_checkpoints.sqlite3"),
        deepseek_api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
        deepseek_base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        ark_api_token=os.environ.get("ARK_API_TOKEN", ""),
        ark_base_url=os.environ.get("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3"),
        ark_model=os.environ.get("ARK_MODEL", "doubao-seed-2-0-lite-260428"),
        jwt_secret=os.environ.get("JWT_SECRET", ""),
    )


def get_bool_env(name, default=False):
    return os.environ.get(name, str(default)).lower() in {"1", "true", "yes", "on"}
