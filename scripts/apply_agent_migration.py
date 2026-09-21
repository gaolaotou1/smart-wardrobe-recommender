from pathlib import Path
import argparse

from agent_v2_preflight import PROJECT_ROOT, connect, load_env_file


def statements(sql: str):
    buffer = []
    for line in sql.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        buffer.append(line)
        if stripped.endswith(";"):
            yield "\n".join(buffer).rstrip(";\n ")
            buffer = []
    if buffer:
        yield "\n".join(buffer)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("migration", nargs="?", default="001_agent_v2.sql")
    args = parser.parse_args()
    load_env_file()
    path = Path(PROJECT_ROOT) / "migrations" / args.migration
    migration = path.read_text(encoding="utf-8")
    with connect() as connection:
        with connection.cursor() as cursor:
            for index, statement in enumerate(statements(migration), 1):
                cursor.execute(statement)
                print(f"applied statement {index}")
        connection.commit()


if __name__ == "__main__":
    main()
