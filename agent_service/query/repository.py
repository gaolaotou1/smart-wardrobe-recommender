from .compiler import compile_query, escape_like
from .semantic import garment_role
from .spec import Aggregate, QuerySpec, SavedOutfitQuery


class WardrobeRepository:
    def __init__(self, connect):
        self.connect = connect

    def search_wardrobe(self, user_id: int, spec: QuerySpec):
        if "occasion" in spec.group_by:
            return self.aggregate_occasions(user_id, spec)
        sql, params = compile_query(spec, user_id)
        with self.connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SET SESSION MAX_EXECUTION_TIME=3000")
                cursor.execute(sql, params)
                if spec.aggregates:
                    if spec.group_by:
                        rows = cursor.fetchall()
                        groups = []
                        for row in rows:
                            values = [row[f"group_value_{index}"] for index in range(1, len(spec.group_by) + 1)]
                            aggregates = {item.alias: row[item.alias] for item in spec.aggregates}
                            groups.append({
                                "group_value": values[0] if len(values) == 1 else dict(zip(spec.group_by, values)),
                                "value": aggregates[spec.aggregates[0].alias],
                                "aggregates": aggregates,
                            })
                        return {"total": sum(row["value"] for row in groups), "groups": groups, "items": []}
                    row = cursor.fetchone() or {}
                    aggregates = {item.alias: row.get(item.alias, 0) for item in spec.aggregates}
                    return {
                        "total": aggregates.get("count", next(iter(aggregates.values()), 0)),
                        "aggregates": aggregates,
                        "items": [],
                    }
                rows = cursor.fetchall()
                count_spec = spec.model_copy(update={
                    "projection": [],
                    "group_by": [],
                    "aggregates": [Aggregate(function="count", alias="count")],
                    "order_by": [],
                    "offset": 0,
                })
                count_sql, count_params = compile_query(count_spec, user_id)
                cursor.execute(count_sql, count_params)
                total = cursor.fetchone()["count"]
        has_more = len(rows) > spec.limit
        items = [normalize_clothes(row) for row in rows[: spec.limit]]
        return {"total": total, "returned": len(items), "has_more": has_more, "items": items}

    def aggregate_occasions(self, user_id: int, spec: QuerySpec):
        other_groups = [field for field in spec.group_by if field != "occasion"]
        projection = ["id", "occasion", *other_groups]
        if "garment_role" in projection:
            projection.extend(["category", "sub_category"])
        base_spec = spec.model_copy(update={
            "projection": list(dict.fromkeys(projection)),
            "group_by": [],
            "aggregates": [],
            "limit": 50,
            "offset": 0,
        })
        counts = {}
        offset = 0
        while offset <= 5000:
            evidence = self.search_wardrobe(user_id, base_spec.model_copy(update={"offset": offset}))
            for item in evidence["items"]:
                for occasion in item.get("occasions", []):
                    key = (occasion, *[item.get(field) for field in other_groups])
                    counts[key] = counts.get(key, 0) + 1
            if not evidence["has_more"]:
                break
            offset += base_spec.limit
        groups = [
            {
                "group_value": key[0] if not other_groups else dict(zip(["occasion", *other_groups], key)),
                "value": count,
            }
            for key, count in sorted(counts.items(), key=lambda pair: (-pair[1], str(pair[0])))
        ]
        return {"total": sum(counts.values()), "groups": groups, "items": [], "has_more": False}

    def get_clothes_details(self, user_id: int, clothes_ids: list[int]):
        ids = unique_ints(clothes_ids)[:20]
        if not ids:
            return []
        placeholders = ", ".join(["%s"] * len(ids))
        sql = f"""
            SELECT id, name, image_url, category, sub_category, brand, style,
                   color, sub_color, season, material, occasion, description, thickness
            FROM clothes
            WHERE user_id = %s AND id IN ({placeholders})
            ORDER BY FIELD(id, {placeholders})
        """
        params = [user_id, *ids, *ids]
        with self.connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SET SESSION MAX_EXECUTION_TIME=3000")
                cursor.execute(sql, params)
                return [normalize_clothes(row) for row in cursor.fetchall()]

    def list_all_clothes(self, user_id: int):
        spec = QuerySpec(limit=50)
        return self.search_wardrobe(user_id, spec)["items"]

    def search_saved_outfits(self, user_id: int, query: SavedOutfitQuery | None = None, limit=20):
        query = query or SavedOutfitQuery(limit=limit)
        where = ["o.user_id = %s"]
        params: list[object] = [user_id]
        if query.outfit_ids:
            where.append(f"o.id IN ({', '.join(['%s'] * len(query.outfit_ids))})")
            params.extend(query.outfit_ids)
        if query.name_contains:
            where.append("o.name LIKE %s ESCAPE '\\\\'")
            params.append("%" + escape_like(query.name_contains) + "%")
        if query.contains_clothes_ids:
            where.append(
                "EXISTS (SELECT 1 FROM outfit_clothes f "
                f"WHERE f.outfit_id = o.id AND f.clothes_id IN ({', '.join(['%s'] * len(query.contains_clothes_ids))}))"
            )
            params.extend(query.contains_clothes_ids)
        if query.created_after:
            where.append("o.create_time >= %s")
            params.append(query.created_after)
        sql = """
            SELECT o.id AS outfit_id, o.name AS outfit_name, o.description AS outfit_description,
                   o.image_url AS outfit_image_url, o.create_time AS outfit_create_time,
                   o.update_time AS outfit_update_time,
                   c.id, c.name, c.image_url, c.category, c.sub_category, c.brand, c.style,
                   c.color, c.sub_color, c.season, c.material, c.occasion, c.description,
                   c.thickness, oc.position
            FROM outfits AS o
            LEFT JOIN outfit_clothes AS oc ON o.id = oc.outfit_id
            LEFT JOIN clothes AS c ON c.id = oc.clothes_id AND c.user_id = o.user_id
            WHERE {where_sql}
            ORDER BY o.update_time DESC, o.id DESC
            LIMIT %s
        """.format(where_sql=" AND ".join(where))
        params.append(min(query.limit * 6, 300))
        with self.connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SET SESSION MAX_EXECUTION_TIME=3000")
                cursor.execute(sql, params)
                rows = cursor.fetchall()
        return group_outfits(rows, query.limit)

    def create_outfit(self, user_id: int, name: str, description: str, clothes_ids: list[int]):
        clothes = self.get_clothes_details(user_id, clothes_ids)
        if len(clothes) != len(unique_ints(clothes_ids)):
            raise ValueError("穿搭中包含不存在或不属于当前用户的衣物")

        image_url = next((item["image_url"] for item in clothes if item.get("image_url")), "")
        with self.connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO outfits (name, description, image_url, user_id) VALUES (%s, %s, %s, %s)",
                    (name, description, image_url, user_id),
                )
                outfit_id = cursor.lastrowid
                for item in clothes:
                    cursor.execute(
                        "INSERT INTO outfit_clothes (outfit_id, clothes_id, position) VALUES (%s, %s, %s)",
                        (outfit_id, item["id"], item["category"]),
                    )
            conn.commit()
        return {"id": outfit_id, "name": name, "description": description, "clothes": clothes}


def normalize_clothes(row):
    item = dict(row)
    occasion = item.get("occasion") or ""
    item["occasions"] = [part.strip() for part in occasion.replace("，", ",").split(",") if part.strip()]
    item["garment_role"] = garment_role(item)
    item["subCategory"] = item.get("sub_category") or ""
    item["subColor"] = item.get("sub_color") or ""
    return item


def group_outfits(rows, limit):
    grouped = {}
    for row in rows:
        outfit_id = row["outfit_id"]
        outfit = grouped.setdefault(
            outfit_id,
            {
                "id": outfit_id,
                "name": row.get("outfit_name") or "未命名穿搭",
                "description": row.get("outfit_description") or "",
                "image_url": row.get("outfit_image_url") or "",
                "updated_at": str(row.get("outfit_update_time")),
                "clothes": [],
            },
        )
        if row.get("id"):
            outfit["clothes"].append(normalize_clothes(row))
    return list(grouped.values())[:limit]


def unique_ints(values):
    result = []
    for value in values:
        number = int(value)
        if number not in result:
            result.append(number)
    return result
