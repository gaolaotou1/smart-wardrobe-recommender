from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from agent_service.query.spec import QuerySpec


RouteName = Literal[
    "wardrobe_query", "outfit_recommendation", "image_analysis",
    "fashion_qa", "outfit_management",
]
SeasonValue = Literal["spring_and_autumn", "summer", "winter", "all_season"]
OccasionValue = Literal[
    "旅行度假场合", "都市休闲场合", "户外运动场合",
    "日常社交场合", "商务交流场合", "正式职业场合",
]
StyleValue = Literal["简约", "休闲", "正式", "优雅", "运动"]


class AttachmentRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["image"]
    url: str | None = None
    upload_id: str | None = Field(default=None, pattern=r"^up_[0-9a-f]{32}$")

    @model_validator(mode="after")
    def validate_reference(self):
        if bool(self.url) == bool(self.upload_id):
            raise ValueError("url 和 upload_id 必须且只能提供一个")
        if self.url and not self.url.startswith("https://"):
            raise ValueError("外部图片必须使用 HTTPS")
        return self


class MessageRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    client_message_id: str = Field(min_length=1, max_length=64)
    text: str = Field(min_length=1, max_length=8_000)
    attachments: list[AttachmentRef] = Field(default_factory=list, max_length=1)
    selected_clothes_ids: list[int] = Field(default_factory=list, max_length=20)


class RouteTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(pattern=r"^t[1-5]$")
    route: RouteName
    sub_intent: str = Field(max_length=80)
    objective: str = Field(max_length=240)
    depends_on: list[str] = Field(default_factory=list, max_length=4)
    required_evidence: list[Literal[
        "count", "list", "one_unambiguous_clothes_id", "comparison",
        "at_least_one_valid_outfit", "image_attributes", "knowledge_answer", "mutation",
    ]] = Field(default_factory=list)


class ConversationSlots(BaseModel):
    model_config = ConfigDict(extra="forbid")

    garment_roles: list[Literal["top", "bottom", "suit", "outerwear"]] = Field(default_factory=list)
    occasion: list[OccasionValue] = Field(default_factory=list)
    style: list[StyleValue] = Field(default_factory=list)
    colors: list[str] = Field(default_factory=list)
    season: SeasonValue | None = None
    weather_needed: bool = False
    location: str | None = None
    seed_clothes_ids: list[int] = Field(default_factory=list)
    excluded_clothes_ids: list[int] = Field(default_factory=list)
    result_limit: int = Field(default=3, ge=1, le=5)


class RouteDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    route_version: Literal["1.0"] = "1.0"
    primary_route: RouteName
    tasks: list[RouteTask] = Field(min_length=1, max_length=5)
    slots: ConversationSlots = Field(default_factory=ConversationSlots)
    query_spec: QuerySpec | None = None
    needs_clarification: bool = False
    clarification_question: str | None = Field(default=None, max_length=240)
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_dag(self):
        ids = [task.task_id for task in self.tasks]
        if len(ids) != len(set(ids)):
            raise ValueError("任务 ID 不得重复")
        known = set(ids)
        edges = {task.task_id: set(task.depends_on) for task in self.tasks}
        if any(not deps <= known for deps in edges.values()):
            raise ValueError("depends_on 引用了不存在的任务")
        visiting: set[str] = set()
        visited: set[str] = set()

        def walk(node: str):
            if node in visiting:
                raise ValueError("任务依赖不得成环")
            if node in visited:
                return
            visiting.add(node)
            for dependency in edges[node]:
                walk(dependency)
            visiting.remove(node)
            visited.add(node)

        for task_id in ids:
            walk(task_id)
        if self.query_spec and self.primary_route != "wardrobe_query":
            raise ValueError("只有简单衣橱查询可携带 query_spec")
        if self.needs_clarification and not self.clarification_question:
            raise ValueError("需要澄清时必须提供一个问题")
        return self


class PlanStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: str
    task_id: str
    action: Literal[
        "search_wardrobe", "aggregate_wardrobe", "get_clothes_details",
        "search_saved_outfits", "recommend_outfits", "analyze_image",
        "get_weather", "prepare_outfit_change",
    ]
    args: dict = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)
    required_evidence: list[str] = Field(default_factory=list)
    hard_constraints: list[str] = Field(default_factory=list)
    relaxable_constraints: list[str] = Field(default_factory=list)


class ExecutionPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: str
    steps: list[PlanStep] = Field(min_length=1, max_length=8)
    answer_when: list[str] = Field(default_factory=list)
    ask_user_when: list[str] = Field(default_factory=list)


class ClothesCard(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    name: str
    image_url: str | None = None
    category: str | None = None
    garment_role: str | None = None


class SupportedFact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    label: str
    value: int | str | float
    evidence_id: str


class PendingActionView(BaseModel):
    action_id: str
    kind: str
    summary: str
    name: str = ""
    clothes_ids: list[int] = Field(default_factory=list)
    expires_at: float
    payload_hash: str


class AgentAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    answer: str
    message: str
    route: RouteName
    completed_tasks: list[str] = Field(default_factory=list)
    partial: bool = False
    cards: list[dict] = Field(default_factory=list)
    outfits: list[dict] = Field(default_factory=list)
    analysis: dict | None = None
    facts: list[SupportedFact] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    pending_action: PendingActionView | None = None
    follow_up_suggestions: list[str] = Field(default_factory=list, max_length=3)
    recommended_images: list[str] = Field(default_factory=list)
