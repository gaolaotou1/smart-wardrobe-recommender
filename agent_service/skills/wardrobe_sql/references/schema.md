# QuerySpec 1.0 Schema Notes

## Source

`source` is always `clothes` for wardrobe item queries.

## Projection Fields

- `id`: stable clothes id.
- `name`: clothes name.
- `image_url`: item image.
- `garment_role`: virtual role, derived by the server.
- `category`: database category, one of `上装`, `下装`, `套装`.
- `sub_category`: detailed category.
- `brand`: optional brand, often missing.
- `style`: style tag.
- `color`: broad color family.
- `sub_color`: precise color.
- `season`: one of `spring_and_autumn`, `summer`, `winter`, `all_season`.
- `material`: fabric/material tag.
- `occasion`: comma-separated multi-value occasion string.
- `description`: user/AI description.
- `thickness`: thickness tag.
- `created_at`: maps to `create_time`.
- `updated_at`: maps to `update_time`.

## Filter Fields

Use only these fields:

`id`, `name`, `garment_role`, `category`, `sub_category`, `brand`, `style`, `color`, `sub_color`, `season`, `material`, `occasion`, `description`, `thickness`, `created_at`, `updated_at`.

## Operators

- `eq`: exact match for scalar fields.
- `in`: finite list match.
- `contains`: text contains or one occasion value.
- `contains_any`: any of several occasion values.
- `contains_all`: all listed occasion values.
- `gte`, `lte`, `between`: dates only.
- `is_null`, `not_null`: missing field checks.

## Aggregates

Use `aggregate: "count"` for quantity questions. Grouping is only allowed for finite fields such as `category`, `garment_role`, `style`, `color`, `season`, `material`, `thickness`, and application-split `occasion`.
