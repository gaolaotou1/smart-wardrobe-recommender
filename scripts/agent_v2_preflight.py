import json
import os
import sys

import pymysql

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_env_file(env_path=os.path.join(PROJECT_ROOT, ".env")):
    if not os.path.exists(env_path):
        return
    with open(env_path, encoding="utf-8") as env_file:
        for line in env_file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def connect():
    return pymysql.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", "3306")),
        user=os.environ.get("DB_USER", "root"),
        password=os.environ.get("DB_PASSWORD", ""),
        database=os.environ.get("DB_NAME", "fashion_system"),
        charset=os.environ.get("DB_CHARSET", "utf8mb4"),
        cursorclass=pymysql.cursors.DictCursor,
    )


def main():
    load_env_file()
    with connect() as conn:
        report = {
            "tables": show_create_tables(conn),
            "duplicate_outfit_clothes": duplicate_outfit_clothes(conn),
            "existing_indexes": existing_indexes(conn),
        }
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    if report["duplicate_outfit_clothes"]:
        print("发现重复 outfit_clothes 关系，请先人工去重再执行唯一约束迁移。", file=sys.stderr)
        return 1
    return 0


def show_create_tables(conn):
    tables = {}
    with conn.cursor() as cursor:
        for table in ("users", "clothes", "outfits", "outfit_clothes"):
            cursor.execute(f"SHOW CREATE TABLE {table}")
            row = cursor.fetchone()
            tables[table] = row.get("Create Table")
    return tables


def duplicate_outfit_clothes(conn):
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT outfit_id, clothes_id, COUNT(*) AS duplicate_count
            FROM outfit_clothes
            GROUP BY outfit_id, clothes_id
            HAVING COUNT(*) > 1
            """
        )
        return cursor.fetchall()


def existing_indexes(conn):
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT table_name, index_name, GROUP_CONCAT(column_name ORDER BY seq_in_index) AS columns
            FROM information_schema.statistics
            WHERE table_schema = DATABASE()
              AND table_name IN ('clothes', 'outfits', 'outfit_clothes')
            GROUP BY table_name, index_name
            ORDER BY table_name, index_name
            """
        )
        return cursor.fetchall()


if __name__ == "__main__":
    raise SystemExit(main())
