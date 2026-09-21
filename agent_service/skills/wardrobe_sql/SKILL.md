# Wardrobe Query Skill

## When to Use

Use this skill when the user asks about their own wardrobe, saved outfits, clothing counts, filtered lists, comparisons, statistics, or any question containing phrases like “我的衣柜”, “我有几件”, “有哪些”, “有没有”, “找出”.

Do not use it for pure fashion knowledge questions such as “藏蓝配什么颜色” unless the user asks about their own clothes.

## Output Contract

Only output QuerySpec 1.0 JSON. Never output SQL.

Do not include `user_id`; the server injects it from the authenticated principal.

Select only the fields needed to answer the question. Avoid broad projection unless the user asks for details or cards.

Use:

- `aggregate: "count"` for quantity questions.
- `garment_role` for semantic roles `top`, `bottom`, `suit`, `outerwear`.
- `occasion` with `contains` or `contains_any`; the database stores comma-separated values.
- `season in ["winter", "all_season"]` when the user says winter.

If a condition cannot be mapped safely, put it in `text_query` only when it is a short clothing-related phrase. Do not invent fields or enum values.

## Semantics

- Outerwear is not a database category. It is `category="上装"` plus an outerwear `sub_category`.
- `occasion` is multi-value text. Never use equality for it.
- Missing `brand` means “未记录品牌”, not “无品牌”.
- The model must not generate SQL, table names, joins, write operations, or authentication fields.

## References

- `references/schema.md`: queryable fields and meanings.
- `references/values.yaml`: allowed values, role mapping, and synonyms.
- `references/examples.yaml`: natural language to QuerySpec examples.
