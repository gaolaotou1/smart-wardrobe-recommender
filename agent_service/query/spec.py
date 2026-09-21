from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .semantic import detect_colors, detect_occasions, detect_roles, detect_seasons


ProjectionField = Literal[
    "id", "name", "image_url", "garment_role", "category", "sub_category",
    "brand", "style", "color", "sub_color", "season", "material",
    "occasion", "description", "thickness", "created_at", "updated_at",
]
FilterField = Literal[
    "id", "name", "garment_role", "category", "sub_category", "brand",
    "style", "color", "sub_color", "season", "material", "occasion",
    "description", "thickness", "created_at", "updated_at",
]
GroupField = Literal[
    "garment_role", "category", "sub_category", "brand", "style", "color",
    "season", "material", "occasion", "thickness",
]


class QueryFilter(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    field: FilterField
    op: Literal[
        "eq", "neq", "in", "contains", "contains_any", "contains_all",
        "prefix", "gte", "lte", "between", "is_null", "not_null",
    ]
    value: str | int | list[str] | list[int] | None = None

    @model_validator(mode="after")
    def validate_operator_value(self):
        if self.op in {"is_null", "not_null"}:
            return self
        if self.value is None:
            raise ValueError(f"{self.op} 运算符需要 value")
        if self.op in {"in", "contains_any", "contains_all", "between"}:
            if not isinstance(self.value, list) or not self.value:
                raise ValueError(f"{self.op} 运算符需要非空数组")
            if len(self.value) > 50:
                raise ValueError("IN 类过滤值最多 50 项")
        if self.op == "between" and len(self.value) != 2:
            raise ValueError("between 必须恰好提供两个值")
        return self


class Aggregate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    function: Literal["count", "count_distinct", "min", "max"]
    field: ProjectionField | None = None
    alias: Literal["count", "distinct_count", "min_value", "max_value"]


class OrderBy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    field: Literal["id", "name", "created_at", "updated_at"]
    direction: Literal["asc", "desc"] = "desc"


class QuerySpec(BaseModel):
    """The only query language exposed to a model. It deliberately is not SQL."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal["1.0"] = "1.0"
    source: Literal["clothes"] = "clothes"
    projection: list[ProjectionField] = Field(default_factory=lambda: [
        "id", "name", "image_url", "category", "sub_category", "style",
        "color", "sub_color", "season", "material", "occasion",
        "description", "thickness",
    ])
    filters: list[QueryFilter] = Field(default_factory=list)
    text_query: str | None = Field(default=None, min_length=1, max_length=64)
    group_by: list[GroupField] = Field(default_factory=list, max_length=2)
    aggregates: list[Aggregate] = Field(default_factory=list, max_length=3)
    order_by: list[OrderBy] = Field(default_factory=list, max_length=2)
    limit: int = Field(default=20, ge=1, le=50)
    offset: int = Field(default=0, ge=0, le=5000)

    @model_validator(mode="before")
    @classmethod
    def accept_v01_shorthand(cls, data: Any):
        """Keep existing golden examples compatible while emitting QuerySpec 1.0."""
        if not isinstance(data, dict):
            return data
        value = dict(data)
        aggregate = value.pop("aggregate", None)
        group = value.get("group_by")
        if isinstance(group, str):
            value["group_by"] = [group]
        if aggregate and not value.get("aggregates"):
            value["aggregates"] = [{"function": aggregate, "alias": "count"}]
        return value

    @model_validator(mode="after")
    def validate_shape(self):
        if not self.aggregates and not self.projection:
            raise ValueError("普通查询必须有 projection")
        if self.group_by and not self.aggregates:
            raise ValueError("group_by 必须与 aggregates 一起使用")
        if "garment_role" in self.projection:
            required = {"category", "sub_category"}
            if not required.issubset(self.projection):
                raise ValueError("投影 garment_role 时必须同时投影 category/sub_category")
        aliases = [item.alias for item in self.aggregates]
        if len(aliases) != len(set(aliases)):
            raise ValueError("聚合别名不得重复")
        if "occasion" in self.group_by and any(item.function != "count" for item in self.aggregates):
            raise ValueError("occasion 应用层分组只支持 count")
        return self

    @property
    def aggregate(self) -> str | None:
        return self.aggregates[0].function if self.aggregates else None


class QueryExecutionContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    authenticated_user_id: int = Field(gt=0)
    request_id: str
    statement_timeout_ms: int = Field(default=3000, ge=100, le=10_000)
    max_rows: int = Field(default=50, ge=1, le=50)


class SavedOutfitQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    outfit_ids: list[int] = Field(default_factory=list, max_length=20)
    name_contains: str | None = Field(default=None, max_length=100)
    contains_clothes_ids: list[int] = Field(default_factory=list, max_length=20)
    created_after: datetime | None = None
    limit: int = Field(default=20, ge=1, le=50)


COUNT_WORDS = ("几件", "多少", "数量", "总数", "统计")


def query_kind(text: str) -> str:
    return "count" if any(word in text for word in COUNT_WORDS) else "list"


def spec_from_text(text: str, limit: int = 20) -> QuerySpec:
    filters: list[QueryFilter] = []
    for field, values in (
        ("garment_role", detect_roles(text)),
        ("season", detect_seasons(text)),
        ("occasion", detect_occasions(text)),
        ("color", detect_colors(text)),
    ):
        if values:
            op = "contains_any" if field == "occasion" else "in"
            filters.append(QueryFilter(field=field, op=op, value=values))

    if query_kind(text) == "count":
        return QuerySpec(projection=[], filters=filters, aggregates=[Aggregate(function="count", alias="count")])
    return QuerySpec(filters=filters, limit=limit)
