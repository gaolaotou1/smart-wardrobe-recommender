import json
from datetime import datetime
from pathlib import Path

from agent_v2_preflight import PROJECT_ROOT, connect, load_env_file


TABLES = ("users", "clothes", "outfits", "outfit_clothes")


def main():
    load_env_file()
    backup = {"created_at": datetime.now().isoformat(), "tables": {}}
    with connect() as connection:
        with connection.cursor() as cursor:
            for table in TABLES:
                cursor.execute(f"SHOW CREATE TABLE `{table}`")
                schema = cursor.fetchone()["Create Table"]
                cursor.execute(f"SELECT * FROM `{table}`")
                backup["tables"][table] = {"schema": schema, "rows": cursor.fetchall()}

    directory = Path(PROJECT_ROOT) / "data" / "backups"
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"before_agent_v2_{datetime.now():%Y%m%d_%H%M%S}.json"
    target.write_text(json.dumps(backup, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(target)


if __name__ == "__main__":
    main()
