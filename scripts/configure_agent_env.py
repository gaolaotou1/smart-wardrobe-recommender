import argparse
import getpass
import secrets
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
DEFAULTS = {
    "VITE_AGENT_API_BASE_URL": "http://localhost:8090",
    "TEXT_MODEL_PROVIDER": "deepseek",
    "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
    "AGENT_MODEL": "deepseek-v4-flash",
    "FAST_MODEL": "deepseek-v4-flash",
    "ARK_BASE_URL": "https://ark.cn-beijing.volces.com/api/v3",
    "ARK_MODEL": "doubao-seed-2-0-lite-260428",
    "ARK_TEXT_MODEL": "doubao-seed-2-0-lite-260428",
    "AGENT_CHECKPOINT_PATH": "./data/langgraph_checkpoints.sqlite3",
    "AGENT_MAX_REPLANS": "2",
    "AGENT_MAX_TOOL_CALLS": "8",
    "AGENT_RUN_TIMEOUT_SECONDS": "90",
    "MEMORY_GATE_INTERVAL_TURNS": "10",
    "CHAT_V2_ENABLED": "true",
    "RECOMMENDATION_V2_ENABLED": "true",
    "IMAGE_ANALYSIS_ENABLED": "true",
    "LONG_TERM_MEMORY_ENABLED": "true",
    "OUTFIT_MUTATIONS_ENABLED": "true",
    "WEATHER_ENABLED": "true",
    "SEMANTIC_RECALL_ENABLED": "false",
    "ADVANCED_READONLY_SQL_ENABLED": "false",
}


def read_env():
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines() if ENV_PATH.exists() else []
    values = {}
    for line in lines:
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return lines, values


def write_env(lines, updates):
    remaining = dict(updates)
    rendered = []
    for line in lines:
        if "=" not in line or line.lstrip().startswith("#"):
            rendered.append(line)
            continue
        key = line.split("=", 1)[0].strip()
        rendered.append(f"{key}={remaining.pop(key)}" if key in remaining else line)
    if remaining:
        rendered.extend(["", "# Agent V2"])
        rendered.extend(f"{key}={value}" for key, value in remaining.items())
    ENV_PATH.write_text("\n".join(rendered).rstrip() + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="安全补齐 Agent V2 的本地 .env")
    parser.add_argument("--defaults-only", action="store_true", help="只写非敏感默认值并生成 JWT secret")
    parser.add_argument("--replace-keys", action="store_true", help="安全替换已有的 API Key（输入不回显）")
    args = parser.parse_args()
    lines, values = read_env()
    updates = dict(DEFAULTS)
    if len(values.get("JWT_SECRET", "")) < 32 or values.get("JWT_SECRET", "").startswith("replace_"):
        updates["JWT_SECRET"] = secrets.token_urlsafe(48)
    if not args.defaults_only:
        for key, label in (("DEEPSEEK_API_KEY", "DeepSeek API Key"), ("ARK_API_TOKEN", "火山方舟 API Token")):
            if args.replace_keys or not values.get(key):
                value = getpass.getpass(f"{label}（输入不回显）: ").strip()
                if value:
                    updates[key] = value
    write_env(lines, updates)
    print(f"已更新 {ENV_PATH}，未打印任何密钥。")


if __name__ == "__main__":
    main()
