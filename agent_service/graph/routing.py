import json
import re
from pathlib import Path

from pydantic import ValidationError

from agent_service.chat.schemas import (
    ConversationSlots,
    ExecutionPlan,
    PlanStep,
    RouteDecision,
    RouteTask,
)
from agent_service.query.semantic import detect_colors, detect_occasions, detect_roles, detect_seasons, detect_styles
from agent_service.query.spec import spec_from_text


SQL_SKILL = (Path(__file__).resolve().parents[1] / "skills" / "wardrobe_sql" / "SKILL.md").read_text(encoding="utf-8")

ROUTER_SYSTEM = """
你是智能衣橱的结构化路由器，只做意图、任务和槽位抽取，不回答问题、不生成 SQL、不生成 user_id。
顶层路由只能是 wardrobe_query、outfit_recommendation、image_analysis、fashion_qa、outfit_management。
一句话可以拆成 1–5 个有依赖的任务。只有关键歧义会改变工具或结果时才澄清。
涉及“我的/衣橱”的事实必须查数据库；纯通用服饰知识不查数据库。
穿搭新增、修改、删除只能准备待确认操作，不能认定用户已确认。
""".strip()


async def route_with_model(model, text: str, context: list[dict], attachments: list[dict]):
    messages = [*context[-8:], {"role": "user", "content": text}]
    if attachments:
        messages.append({"role": "user", "content": f"本轮附件数：{len(attachments)}，类型：image"})
    schema = RouteDecision.model_json_schema()
    result = await model.structured(
        purpose="router",
        system=ROUTER_SYSTEM + "\n\n" + SQL_SKILL,
        messages=messages,
        schema=schema,
    )
    try:
        decision = RouteDecision.model_validate(result.content)
        return stabilize_decision(decision, text, attachments), [result]
    except ValidationError as first_error:
        repair = await model.structured(
            purpose="router_repair",
            system=ROUTER_SYSTEM + "\n\n" + SQL_SKILL,
            messages=[{
                "role": "user",
                "content": "修复这份 JSON："
                + result.raw_text
                + "\n校验错误："
                + json.dumps(first_error.errors(include_url=False), ensure_ascii=False),
            }],
            schema=schema,
        )
        decision = RouteDecision.model_validate(repair.content)
        return stabilize_decision(decision, text, attachments), [result, repair]


def deterministic_route(text: str, attachments: list[dict] | None = None) -> RouteDecision:
    attachments = attachments or []
    clauses = [text] if attachments else [part.strip() for part in re.split(r"[，；;、]|然后|再|并且", text) if part.strip()]
    routes = [classify_clause(part, bool(attachments)) for part in clauses] or [classify_clause(text, bool(attachments))]
    tasks = []
    for index, route in enumerate(routes[:5], 1):
        required = evidence_for_route(route, text)
        tasks.append(RouteTask(
            task_id=f"t{index}",
            route=route,
            sub_intent=sub_intent(route, text),
            objective=clauses[index - 1] if index <= len(clauses) else text,
            depends_on=[f"t{index - 1}"] if index > 1 else [],
            required_evidence=required,
        ))

    primary = routes[-1] if len(routes) > 1 else routes[0]
    roles = detect_roles(text)
    seasons = detect_seasons(text)
    weather_needed = any(word in text for word in ("天气", "气温", "下雨", "今天穿", "明天穿"))
    location = extract_location(text)
    slots = ConversationSlots(
        garment_roles=roles,
        occasion=detect_occasions(text),
        style=detect_styles(text),
        colors=detect_colors(text),
        season=seasons[0] if seasons else None,
        weather_needed=weather_needed,
        location=location,
        seed_clothes_ids=[int(value) for value in re.findall(r"#?(\d+)", text)][:20],
        result_limit=extract_result_limit(text),
    )
    vague_event = text.rstrip("？?") in {"给我搭一套参加活动的", "参加活动怎么穿"}
    needs_clarification = vague_event or (weather_needed and not location)
    return RouteDecision(
        primary_route=primary,
        tasks=tasks,
        slots=slots,
        query_spec=spec_from_text(text) if len(tasks) == 1 and primary == "wardrobe_query" else None,
        needs_clarification=needs_clarification,
        clarification_question=(
            "你要去哪个城市？告诉我城市就能结合天气推荐。"
            if weather_needed and not location else
            "这个活动更偏正式、商务，还是休闲呢？" if vague_event else None
        ),
        confidence=0.78,
    )


def stabilize_decision(decision: RouteDecision, text: str, attachments: list[dict]) -> RouteDecision:
    deterministic = deterministic_route(text, attachments)
    slots = decision.slots.model_copy(update={
        "garment_roles": deterministic.slots.garment_roles or decision.slots.garment_roles,
        "occasion": deterministic.slots.occasion or decision.slots.occasion,
        "style": deterministic.slots.style or decision.slots.style,
        "colors": deterministic.slots.colors or decision.slots.colors,
        "season": deterministic.slots.season or decision.slots.season,
        "weather_needed": deterministic.slots.weather_needed or decision.slots.weather_needed,
        "location": deterministic.slots.location or decision.slots.location,
        "result_limit": deterministic.slots.result_limit,
    })
    query_spec = stabilize_query_spec(decision.query_spec, text)
    if query_spec is None and len(decision.tasks) == 1 and decision.tasks[0].route == "wardrobe_query":
        query_spec = spec_from_text(text)
    updates = {"slots": slots, "query_spec": query_spec}
    if deterministic.needs_clarification:
        updates.update({
            "needs_clarification": True,
            "clarification_question": deterministic.clarification_question,
        })
    return decision.model_copy(update=updates)


def stabilize_query_spec(spec, text):
    if spec is None:
        return None
    canonical = spec_from_text(text, limit=spec.limit)
    canonical_fields = {item.field for item in canonical.filters}
    filters = [item for item in spec.filters if item.field not in canonical_fields]
    filters.extend(canonical.filters)
    updates = {"filters": filters}
    if canonical.aggregates and not spec.aggregates:
        updates.update({"projection": [], "aggregates": canonical.aggregates})
    return spec.model_copy(update=updates)


def make_execution_plan(decision: RouteDecision) -> ExecutionPlan:
    action_by_route = {
        "wardrobe_query": "aggregate_wardrobe" if decision.query_spec and decision.query_spec.aggregates else "search_wardrobe",
        "outfit_recommendation": "recommend_outfits",
        "image_analysis": "analyze_image",
        "fashion_qa": "get_clothes_details" if any("personal" in task.sub_intent for task in decision.tasks) else "search_wardrobe",
        "outfit_management": "prepare_outfit_change",
    }
    steps = []
    task_last_step = {}
    for task in decision.tasks:
        args = {"query_spec": decision.query_spec.model_dump(mode="json")} if task.route == "wardrobe_query" and decision.query_spec else {}
        dependency_steps = [task_last_step[item] for item in task.depends_on]
        if task.route == "outfit_recommendation" and decision.slots.weather_needed:
            weather_step = f"s{len(steps) + 1}"
            steps.append(PlanStep(
                step_id=weather_step,
                task_id=task.task_id,
                action="get_weather",
                args={"location": decision.slots.location},
                depends_on=dependency_steps,
                required_evidence=["weather"],
            ))
            dependency_steps = [weather_step]
        step_id = f"s{len(steps) + 1}"
        steps.append(PlanStep(
            step_id=step_id,
            task_id=task.task_id,
            action=action_by_route[task.route],
            args=args,
            depends_on=dependency_steps,
            required_evidence=list(task.required_evidence),
        ))
        task_last_step[task.task_id] = step_id
    return ExecutionPlan(
        goal="；".join(task.objective for task in decision.tasks),
        steps=steps,
        answer_when=[item for task in decision.tasks for item in task.required_evidence],
        ask_user_when=["关键槽位只能由用户决定"],
    )


def classify_clause(text: str, has_image: bool) -> str:
    if has_image or any(word in text for word in ("这张图", "图片", "这件衣服是什么")):
        return "image_analysis"
    if any(word in text for word in ("保存", "存下来", "存为", "重命名", "删除穿搭", "已保存", "我的穿搭")):
        return "outfit_management"
    if any(word in text for word in ("搭配", "推荐", "穿搭", "怎么穿", "穿什么", "今天穿", "明天穿", "配一套", "面试穿", "通勤装")):
        return "outfit_recommendation"
    if any(word in text for word in ("几件", "多少", "有哪些", "有没有", "找", "列", "衣橱", "我的衣")):
        return "wardrobe_query"
    return "fashion_qa"


def sub_intent(route: str, text: str) -> str:
    if route == "wardrobe_query":
        return "count" if any(word in text for word in ("几件", "多少", "数量", "统计")) else "list"
    if route == "outfit_recommendation":
        return "seeded_recommendation" if re.search(r"#?\d+", text) else "from_scratch"
    if route == "image_analysis":
        return "analyze_and_search" if any(word in text for word in ("我有", "衣橱", "类似")) else "analyze"
    if route == "outfit_management":
        return "list_saved" if any(word in text for word in ("已保存", "我的穿搭")) else "prepare_change"
    return "knowledge"


def evidence_for_route(route: str, text: str) -> list[str]:
    if route == "wardrobe_query":
        return ["count" if any(word in text for word in ("几件", "多少", "数量", "统计")) else "list"]
    return {
        "outfit_recommendation": ["at_least_one_valid_outfit"],
        "image_analysis": ["image_attributes"],
        "fashion_qa": ["knowledge_answer"],
        "outfit_management": ["mutation"],
    }[route]


def extract_result_limit(text: str) -> int:
    for token, value in (("五套", 5), ("5套", 5), ("四套", 4), ("4套", 4), ("三套", 3), ("3套", 3), ("两套", 2), ("二套", 2), ("2套", 2), ("一套", 1), ("1套", 1)):
        if token in text:
            return value
    return 3


def extract_location(text: str) -> str | None:
    for city in ("北京", "上海", "广州", "深圳", "香港", "杭州", "南京", "成都", "武汉", "西安"):
        if city in text:
            return city
    match = re.search(r"(?:在|去)([\u4e00-\u9fff]{2,8}?)(?:今天|明天|后天|出门|穿|旅行|的天气)", text)
    return match.group(1) if match else None
