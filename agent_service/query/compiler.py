from .semantic import OUTERWEAR_SUB_CATEGORIES
from .spec import QuerySpec

CLOTHES_FIELDS = {
    "id": "c.id",
    "name": "c.name",
    "image_url": "c.image_url",
    "category": "c.category",
    "sub_category": "c.sub_category",
    "brand": "c.brand",
    "style": "c.style",
    "color": "c.color",
    "sub_color": "c.sub_color",
    "season": "c.season",
    "material": "c.material",
    "occasion": "c.occasion",
    "description": "c.description",
    "thickness": "c.thickness",
    "created_at": "c.create_time",
    "updated_at": "c.update_time",
}

TEXT_FIELDS = ("c.name", "c.sub_category", "c.brand", "c.style", "c.material", "c.description")
ORDERABLE_FIELDS = {"id", "name", "created_at", "updated_at"}


def compile_query(spec: QuerySpec, user_id: int):
    sql, params = _compile_query(spec, user_id)
    assert_only_allowed_ast(sql)
    return sql, params


def _compile_query(spec: QuerySpec, user_id: int):
    params: list[object] = [user_id]
    where_parts = ["c.user_id = %s"]

    for filter_item in spec.filters:
        where_sql, values = compile_filter(filter_item.field, filter_item.op, filter_item.value)
        where_parts.append(where_sql)
        params.extend(values)

    if spec.text_query:
        text_sql, values = compile_text_query(spec.text_query)
        where_parts.append(text_sql)
        params.extend(values)

    where_sql = " AND ".join(f"({part})" for part in where_parts)

    if spec.aggregates:
        aggregates_sql = ", ".join(
            f"{compile_aggregate(item.function, item.field)} AS {item.alias}"
            for item in spec.aggregates
        )
        if spec.group_by:
            group_sql = [compile_group_by(field) for field in spec.group_by]
            select_groups = ", ".join(
                f"{expression} AS group_value_{index}"
                for index, expression in enumerate(group_sql, 1)
            )
            group_clause = ", ".join(group_sql)
            return (
                f"SELECT {select_groups}, {aggregates_sql} "
                f"FROM clothes AS c WHERE {where_sql} GROUP BY {group_clause} "
                f"ORDER BY {spec.aggregates[0].alias} DESC",
                params,
            )
        return f"SELECT {aggregates_sql} FROM clothes AS c WHERE {where_sql}", params

    projection = ", ".join(CLOTHES_FIELDS[field] for field in spec.projection if field in CLOTHES_FIELDS)
    if not projection:
        raise ValueError("普通查询至少需要一个真实列")
    limit = min(max(int(spec.limit), 1), 50)
    offset = max(int(spec.offset), 0)
    params.extend([limit + 1, offset])
    order_sql = compile_order_by(spec.order_by)
    sql = (
        f"SELECT {projection} "
        f"FROM clothes AS c "
        f"WHERE {where_sql} "
        f"{order_sql} "
        "LIMIT %s OFFSET %s"
    )
    return sql, params


def compile_filter(field, op, value):
    if field == "garment_role":
        return compile_garment_role(op, value)
    if field == "occasion":
        return compile_occasion(op, value)
    if field not in CLOTHES_FIELDS:
        raise ValueError(f"不支持的查询字段: {field}")

    column = CLOTHES_FIELDS[field]
    if op == "eq":
        return f"{column} = %s", [value]
    if op == "neq":
        return f"{column} <> %s", [value]
    if op == "in":
        values = list(value or [])
        if not values:
            raise ValueError("in 不允许空值")
        placeholders = ", ".join(["%s"] * len(values))
        return f"{column} IN ({placeholders})", values
    if op == "contains":
        return f"{column} LIKE %s ESCAPE '\\\\'", [f"%{escape_like(str(value))}%"]
    if op in {"contains_any", "contains_all"}:
        values = list(value or [])
        if not values:
            raise ValueError(f"{op} 不允许空值")
        pieces = [f"{column} LIKE %s ESCAPE '\\\\'" for _ in values]
        joiner = " OR " if op == "contains_any" else " AND "
        return f"({joiner.join(pieces)})", [f"%{escape_like(str(item))}%" for item in values]
    if op == "prefix":
        return f"{column} LIKE %s ESCAPE '\\\\'", [f"{escape_like(str(value))}%"]
    if op in {"gte", "lte"}:
        comparator = ">=" if op == "gte" else "<="
        return f"{column} {comparator} %s", [value]
    if op == "between":
        values = list(value or [])
        if len(values) != 2:
            raise ValueError("between 必须有两个值")
        return f"{column} BETWEEN %s AND %s", values
    if op == "is_null":
        return f"({column} IS NULL OR {column} = '')", []
    if op == "not_null":
        return f"({column} IS NOT NULL AND {column} != '')", []
    raise ValueError(f"不支持的查询运算符: {op}")


def compile_garment_role(op, value):
    if op not in {"eq", "in", "neq"}:
        raise ValueError("garment_role 只支持 eq/in/neq")
    values = list(value or []) if op == "in" else [value]
    role_sql = []
    params: list[object] = []

    if "top" in values:
        placeholders = ", ".join(["%s"] * len(OUTERWEAR_SUB_CATEGORIES))
        role_sql.append(f"(c.category = %s AND COALESCE(c.sub_category, '') NOT IN ({placeholders}))")
        params.extend(["上装", *sorted(OUTERWEAR_SUB_CATEGORIES)])
    if "outerwear" in values:
        placeholders = ", ".join(["%s"] * len(OUTERWEAR_SUB_CATEGORIES))
        role_sql.append(f"(c.category = %s AND c.sub_category IN ({placeholders}))")
        params.extend(["上装", *sorted(OUTERWEAR_SUB_CATEGORIES)])
    if "bottom" in values:
        role_sql.append("c.category = %s")
        params.append("下装")
    if "suit" in values:
        role_sql.append("c.category = %s")
        params.append("套装")

    if not role_sql:
        return "1 = 1", []
    expression = " OR ".join(role_sql)
    return (f"NOT ({expression})" if op == "neq" else expression), params


def compile_occasion(op, value):
    if op not in {"eq", "in", "contains", "contains_any", "contains_all", "neq"}:
        raise ValueError("occasion 运算符不受支持")
    values = list(value or []) if op in {"in", "contains_any", "contains_all"} else [value]
    normalized = [str(item).replace("，", ",").replace(" ", "") for item in values if item]
    pieces = [
        "CONCAT(',', REPLACE(REPLACE(COALESCE(c.occasion, ''), '，', ','), ' ', ''), ',') "
        "LIKE CONCAT('%,', %s, ',%')"
        for _ in normalized
    ]
    if not pieces:
        return "1 = 1", []
    joiner = " OR " if op in {"in", "contains_any"} else " AND "
    expression = joiner.join(pieces)
    return (f"NOT ({expression})" if op == "neq" else expression), normalized


def compile_aggregate(function, field):
    if function == "count" and field is None:
        return "COUNT(*)"
    if field == "garment_role" or field not in CLOTHES_FIELDS:
        raise ValueError("该字段不支持直接聚合")
    column = CLOTHES_FIELDS[field]
    functions = {
        "count": f"COUNT({column})",
        "count_distinct": f"COUNT(DISTINCT {column})",
        "min": f"MIN({column})",
        "max": f"MAX({column})",
    }
    return functions[function]


def compile_text_query(text):
    keyword = f"%{escape_like(text[:64])}%"
    sql = " OR ".join(f"{field} LIKE %s ESCAPE '\\\\'" for field in TEXT_FIELDS)
    return f"({sql})", [keyword] * len(TEXT_FIELDS)


def compile_group_by(field):
    if field == "garment_role":
        outerwear_values = ", ".join(f"'{value}'" for value in sorted(OUTERWEAR_SUB_CATEGORIES))
        return (
            "CASE "
            "WHEN c.category = '下装' THEN 'bottom' "
            "WHEN c.category = '套装' THEN 'suit' "
            f"WHEN c.category = '上装' AND c.sub_category IN ({outerwear_values}) THEN 'outerwear' "
            "WHEN c.category = '上装' THEN 'top' "
            "ELSE 'unknown' END"
        )
    if field not in CLOTHES_FIELDS:
        raise ValueError(f"不支持的分组字段: {field}")
    return CLOTHES_FIELDS[field]


def compile_order_by(order_by):
    if not order_by:
        return "ORDER BY c.update_time DESC, c.id DESC"

    pieces = []
    for item in order_by[:2]:
        if item.field not in ORDERABLE_FIELDS:
            raise ValueError(f"不支持的排序字段: {item.field}")
        direction = "ASC" if item.direction.lower() == "asc" else "DESC"
        pieces.append(f"{CLOTHES_FIELDS[item.field]} {direction}")
    pieces.append("c.id DESC")
    return "ORDER BY " + ", ".join(pieces)


def escape_like(text):
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def assert_only_allowed_ast(sql):
    from sqlglot import exp, parse_one

    parsed = parse_one(sql.replace("%s", "0"), read="mysql")
    if not isinstance(parsed, exp.Select):
        raise ValueError("只允许 SELECT")
    forbidden = (exp.Insert, exp.Update, exp.Delete, exp.Create, exp.Drop, exp.Command)
    if any(parsed.find(node) is not None for node in forbidden):
        raise ValueError("查询 AST 包含不允许的节点")
    tables = {table.name for table in parsed.find_all(exp.Table)}
    if tables != {"clothes"}:
        raise ValueError("查询只能访问 clothes")
