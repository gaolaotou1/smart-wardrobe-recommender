import json
import asyncio
import sys
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent_service.attachments import LocalAttachmentStore
from agent_service.chat.schemas import AttachmentRef
from agent_service.chat.service import WardrobeAgent, is_clothes_mutation, is_outfit_management_request, merge_answers
from agent_service.graph.routing import (
    deterministic_route,
    make_execution_plan,
    stabilize_decision,
    stabilize_query_spec,
)
from agent_service.memory import review_memory_operations
from agent_service.memory_worker import MemoryWorker
from agent_service.models.doubao_vision import (
    is_trusted_image_host,
    response_output_text,
    validate_data_image_url,
    validate_public_https_url,
)
from agent_service.query.compiler import compile_query
from agent_service.query.spec import Aggregate, QueryFilter, QuerySpec
from agent_service.recommendation.engine import recommend_outfits


def main():
    test_routing()
    test_query_compiler()
    test_recommendation()
    test_memory_review()
    test_memory_gate()
    test_vision_boundary()
    test_local_attachment()
    test_answer_merge()
    print("agent smoke tests passed")


def test_routing():
    agent = WardrobeAgent(lambda: None, store=NoopStore())
    path = ROOT / "agent_service/tests/golden/routing_query.jsonl"
    for line in path.read_text(encoding="utf-8").splitlines():
        case = json.loads(line)
        assert agent.route(case["input"]) == case["route"], case
    weather_route = deterministic_route("北京今天穿什么")
    assert weather_route.primary_route == "outfit_recommendation"
    assert weather_route.slots.location == "北京" and weather_route.slots.weather_needed
    assert [step.action for step in make_execution_plan(weather_route).steps] == ["get_weather", "recommend_outfits"]
    image_route = deterministic_route("分析这张图，并看看我衣橱里有没有类似的", [{"type": "image", "upload_id": "up_" + "0" * 32}])
    assert len(image_route.tasks) == 1 and image_route.tasks[0].route == "image_analysis"
    model_missed_clarification = weather_route.model_copy(update={
        "slots": weather_route.slots.model_copy(update={"location": None}),
        "needs_clarification": False,
        "clarification_question": None,
    })
    stabilized = stabilize_decision(model_missed_clarification, "今天穿什么？", [])
    assert stabilized.needs_clarification and "城市" in stabilized.clarification_question
    missing_spec = deterministic_route("列出我的春秋外套").model_copy(update={"query_spec": None})
    restored = stabilize_decision(missing_spec, "列出我的春秋外套", [])
    assert restored.query_spec is not None
    assert is_clothes_mutation("删除我所有衣服")
    assert not is_clothes_mutation("删除穿搭 #3")
    assert is_outfit_management_request("保存第一套为通勤穿搭")


def test_query_compiler():
    spec = QuerySpec(
        filters=(
            QueryFilter(field="garment_role", op="in", value=["outerwear"]),
            QueryFilter(field="season", op="in", value=["winter", "all_season"]),
            QueryFilter(field="occasion", op="contains_any", value=["商务交流场合"]),
        ),
        aggregate="count",
    )
    sql, params = compile_query(spec, 42)
    assert "COUNT(*)" in sql
    assert "user_id" in sql
    assert params[0] == 42

    grouped = QuerySpec(
        projection=[],
        group_by=["garment_role", "season"],
        aggregates=[
            Aggregate(function="count", alias="count"),
            Aggregate(function="count_distinct", field="color", alias="distinct_count"),
        ],
    )
    grouped_sql, grouped_params = compile_query(grouped, 42)
    assert "group_value_1" in grouped_sql and "group_value_2" in grouped_sql
    assert "COUNT(DISTINCT c.color) AS distinct_count" in grouped_sql
    assert grouped_params == [42]

    unstable = QuerySpec(filters=[QueryFilter(field="season", op="eq", value="spring_autumn")])
    stabilized = stabilize_query_spec(unstable, "列出我的春秋外套")
    values = {item.field: item.value for item in stabilized.filters}
    assert values["season"] == ["spring_and_autumn"]
    assert values["garment_role"] == ["outerwear"]


def test_recommendation():
    clothes = [
        item(1, "白衬衫", "top", "白色系", "简约", ["商务交流场合"]),
        item(2, "黑西裤", "bottom", "黑色系", "正式", ["正式职业场合"]),
        item(3, "藏蓝西装", "outerwear", "蓝色系", "正式", ["商务交流场合"]),
    ]
    outfits = recommend_outfits(clothes, "面试通勤", limit=3)
    assert outfits
    assert all({piece["garment_role"] for piece in outfit["clothes"]} - {"top", "bottom", "outerwear", "suit"} == set() for outfit in outfits)
    assert len({outfit["candidate_id"] for outfit in outfits}) == len(outfits)
    refined = recommend_outfits(clothes, "第二套更休闲一点", limit=2)
    assert refined


def test_memory_review():
    operations = review_memory_operations("以后不要给我推荐全黑")
    assert operations
    assert operations[0]["memory_type"] == "avoidance"
    assert review_memory_operations("忘掉我不喜欢全黑这件事") == []


def test_memory_gate():
    class Store:
        @staticmethod
        def memory_gate_context(_user_id, _session_id, _turn_count):
            return {"user_messages": ["以后不要给我推荐全黑", "今天想穿红色"], "active_memories": []}

    class Config:
        long_term_memory_enabled = True
        text_model_provider = "deepseek"
        deepseek_api_key = ""
        ark_api_token = ""

    class Service:
        store = Store()
        config = Config()

    job = {"input": {}, "review_type": "gate", "user_id": 1, "session_id": "s", "turn_from": 1, "turn_to": 10}
    operations = asyncio.run(MemoryWorker(Service()).review(job))
    assert len(operations) == 1
    assert operations[0]["memory_key"] == "outfit.color.all_black"


def test_vision_boundary():
    assert response_output_text({"output_text": '{"ok":true}'}) == '{"ok":true}'
    assert is_trusted_image_host("ark-project.tos-cn-beijing.volces.com")
    assert is_trusted_image_host("pic1.imgdb.cn")
    assert not is_trusted_image_host("imgdb.cn.attacker.example")
    try:
        validate_public_https_url("http://127.0.0.1/private.png")
    except ValueError:
        pass
    else:
        raise AssertionError("SSRF 边界必须拒绝本地 HTTP URL")


def test_local_attachment():
    stream = BytesIO()
    Image.new("RGB", (32, 32), (240, 240, 240)).save(stream, format="PNG")
    with TemporaryDirectory() as directory:
        store = LocalAttachmentStore(directory)
        uploaded = store.save_image(7, stream.getvalue())
        data_url = store.data_url(7, uploaded["upload_id"])
        assert data_url.startswith("data:image/png;base64,")
        validate_data_image_url(data_url)
        try:
            store.data_url(8, uploaded["upload_id"])
        except ValueError:
            pass
        else:
            raise AssertionError("附件必须按用户隔离")
    AttachmentRef(type="image", upload_id="up_" + "0" * 32)
    for invalid in (
        {"type": "image"},
        {"type": "image", "upload_id": "../secret"},
        {"type": "image", "url": "http://127.0.0.1/a.png"},
        {"type": "image", "url": "https://example.com/a.png", "upload_id": "up_" + "0" * 32},
    ):
        try:
            AttachmentRef.model_validate(invalid)
        except ValidationError:
            pass
        else:
            raise AssertionError(f"附件边界未拒绝: {invalid}")


def test_answer_merge():
    base = {
        "session_id": "s", "answer": "ok", "message": "ok", "route": "image_analysis",
        "completed_tasks": ["image_analysis"], "partial": False, "cards": [], "outfits": [],
        "analysis": {"category": "上装"}, "facts": [], "assumptions": [], "warnings": [],
        "evidence_ids": ["e1"], "pending_action": None, "follow_up_suggestions": [],
        "recommended_images": [],
    }
    second = {**base, "route": "wardrobe_query", "analysis": None, "evidence_ids": ["e2"]}
    merged = merge_answers("s", "image_analysis", [base, second])
    assert merged["analysis"] == {"category": "上装"}
    assert merged["evidence_ids"] == ["e1", "e2"]


def item(id_, name, role, color, style, occasions):
    return {
        "id": id_,
        "name": name,
        "image_url": f"https://example.com/{id_}.png",
        "category": "上装" if role in {"top", "outerwear"} else "下装",
        "garment_role": role,
        "season": "all_season",
        "occasions": occasions,
        "color": color,
        "style": style,
    }


class NoopStore:
    pass


if __name__ == "__main__":
    main()
