from .schemas import AgentAnswer


def validate_agent_answer(answer: dict, evidence: list[dict] | None = None):
    parsed = AgentAnswer.model_validate(answer)
    evidence = evidence or []
    evidence_by_id = {item["evidence_id"]: item for item in evidence}
    if not set(parsed.evidence_ids) <= set(evidence_by_id):
        raise ValueError("回答引用了本轮不存在的证据")

    allowed_clothes = {}
    for item in evidence:
        collect_clothes(item.get("data"), allowed_clothes)

    for card in parsed.cards:
        validate_clothes(card, allowed_clothes)
    for outfit in parsed.outfits:
        for clothes in outfit.get("clothes", []):
            validate_clothes(clothes, allowed_clothes)

    allowed_urls = {item.get("image_url") for item in allowed_clothes.values() if item.get("image_url")}
    if any(url not in allowed_urls for url in parsed.recommended_images):
        raise ValueError("回答包含不属于证据衣物的图片")
    for fact in parsed.facts:
        if fact.evidence_id not in evidence_by_id:
            raise ValueError("结构化事实缺少有效证据")
    if parsed.pending_action and any(word in parsed.answer for word in ("已保存", "已删除", "已修改")):
        raise ValueError("待确认操作不得声称已完成")
    return parsed.model_dump(mode="json")


def collect_clothes(value, result):
    if isinstance(value, dict):
        if "id" in value and "name" in value and ("category" in value or "garment_role" in value):
            result[int(value["id"])] = value
        for child in value.values():
            collect_clothes(child, result)
    elif isinstance(value, list):
        for child in value:
            collect_clothes(child, result)


def validate_clothes(item, allowed):
    item_id = int(item.get("id", 0))
    source = allowed.get(item_id)
    if not source:
        raise ValueError(f"回答引用了证据外的衣物 #{item_id}")
    if item.get("image_url") != source.get("image_url"):
        raise ValueError(f"衣物 #{item_id} 的图片与事实源不一致")
