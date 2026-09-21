from itertools import product

from agent_service.query.semantic import detect_occasions, detect_seasons, detect_styles


WEIGHTS = {
    "intent": 0.24,
    "occasion": 0.20,
    "season_weather": 0.18,
    "color": 0.14,
    "style": 0.12,
    "preference": 0.07,
    "saved_prior": 0.05,
}
STYLE_COMPATIBILITY = {
    ("简约", "正式"): 0.90,
    ("简约", "休闲"): 0.85,
    ("优雅", "正式"): 0.85,
    ("休闲", "运动"): 0.85,
    ("正式", "运动"): 0.35,
}
NEUTRAL_COLORS = {"黑色系", "白色系", "灰色系", "黄色系"}
VERSIONS = {
    "retrieval_version": "recall-1.0",
    "score_version": "score-1.0",
    "color_matrix_version": "color-1.0",
    "style_matrix_version": "style-1.0",
    "semantic_dictionary_version": "wardrobe-values-1.0",
}


def recommend_outfits(
    clothes, text, seed_ids=None, limit=3, memories=None, saved_outfits=None,
    required_match_ids=None,
):
    seed_ids = set(seed_ids or [])
    required_match_ids = set(required_match_ids or [])
    existing_ids = {item["id"] for item in clothes}
    if not seed_ids <= existing_ids:
        return []

    seasons = detect_seasons(text)
    occasions = recommendation_occasions(text)
    styles = detect_styles(text)
    pools = split_pools(clothes)
    candidates = generate_candidates(pools, seed_ids)
    scored = []
    for index, items in enumerate(candidates[:200], 1):
        if required_match_ids and not required_match_ids.intersection(item["id"] for item in items):
            continue
        if not hard_constraints_pass(items, seasons, occasions):
            continue
        score, breakdown, confidence = score_candidate(
            items, seasons, occasions, styles, memories or [], saved_outfits or [], seed_ids
        )
        scored.append({
            "candidate_id": f"cand_{index:03d}",
            "name": outfit_name(occasions),
            "score": round(score, 3),
            "score_confidence": round(confidence, 3),
            "score_breakdown": breakdown,
            "hard_constraints_passed": True,
            "reason": explain_candidate(items, breakdown, seasons, occasions),
            "constraints_met": [*occasions, *seasons],
            "caveats": missing_caveats(items),
            "clothes": items,
            "image_urls": [item["image_url"] for item in items if item.get("image_url")],
            "versions": VERSIONS,
        })
    scored.sort(key=lambda item: (item["score"], item["score_confidence"]), reverse=True)
    return diversify_mmr(scored[:20], min(max(int(limit), 1), 5))


def split_pools(clothes):
    pools = {"top": [], "bottom": [], "suit": [], "outerwear": []}
    for item in clothes:
        role = item.get("garment_role")
        if role in pools and len(pools[role]) < 20:
            pools[role].append(item)
    return pools


def recommendation_occasions(text):
    occasions = detect_occasions(text)
    style_refinement = any(
        phrase in text
        for phrase in ("更休闲", "休闲一点", "休闲些", "休闲风格")
    )
    if style_refinement:
        occasions = [value for value in occasions if value != "都市休闲场合"]
    return occasions


def generate_candidates(pools, seed_ids):
    candidates = []
    candidates.extend([list(items) for items in product(pools["top"], pools["bottom"])])
    candidates.extend([list(items) for items in product(pools["top"], pools["bottom"], pools["outerwear"])])
    candidates.extend([[item] for item in pools["suit"]])
    candidates.extend([list(items) for items in product(pools["suit"], pools["outerwear"])])
    unique = {}
    for items in candidates:
        item_ids = frozenset(item["id"] for item in items)
        if seed_ids <= item_ids:
            unique.setdefault(tuple(sorted(item_ids)), items)
    return list(unique.values())


def hard_constraints_pass(items, seasons, occasions):
    roles = [item.get("garment_role") for item in items]
    if roles.count("top") > 1 or roles.count("bottom") > 1 or roles.count("suit") > 1 or roles.count("outerwear") > 1:
        return False
    if "suit" in roles and ("top" in roles or "bottom" in roles):
        return False
    if "outerwear" in roles and not ({"top", "bottom"} <= set(roles) or "suit" in roles):
        return False
    if seasons and any(item.get("season") and season_fit(item, seasons) < 0.25 for item in items):
        return False
    if occasions and any(item.get("occasions") and occasion_fit(item, occasions) < 0.25 for item in items):
        return False
    return True


def score_candidate(items, seasons, occasions, styles, memories, saved_outfits, seed_ids):
    parts = {
        "intent": 1.0 if seed_ids else 0.85,
        "occasion": average(occasion_fit(item, occasions) for item in items) if occasions else 0.6,
        "season_weather": average(season_fit(item, seasons) for item in items) if seasons else 0.6,
        "color": color_harmony(items),
        "style": style_fit(items, styles),
        "preference": preference_fit(items, memories),
        "saved_prior": saved_prior(items, saved_outfits),
    }
    known = {
        "intent": True,
        "occasion": bool(occasions and any(item.get("occasions") for item in items)),
        "season_weather": bool(seasons and any(item.get("season") for item in items)),
        "color": all(item.get("color") for item in items),
        "style": all(item.get("style") for item in items),
        "preference": bool(memories),
        "saved_prior": bool(saved_outfits),
    }
    score = sum(WEIGHTS[key] * parts[key] for key in WEIGHTS)
    confidence = sum(WEIGHTS[key] for key in WEIGHTS if known[key]) / sum(WEIGHTS.values())
    return score, {key: round(value, 2) for key, value in parts.items()}, confidence


def season_fit(item, target_seasons):
    season = item.get("season")
    if not season:
        return 0.5
    if season in target_seasons:
        return 1.0
    if season == "all_season":
        return 0.92
    return 0.2


def occasion_fit(item, target_occasions):
    values = set(item.get("occasions") or [])
    if not values:
        return 0.5
    if values.intersection(target_occasions):
        return 1.0
    if "都市休闲场合" in values and any(x in target_occasions for x in ("商务交流场合", "日常社交场合")):
        return 0.65
    return 0.2


def color_harmony(items):
    colors = [item.get("color") for item in items if item.get("color")]
    if len(colors) < len(items):
        return 0.5
    if len(set(colors)) == 1:
        return 0.86
    if any(color in NEUTRAL_COLORS for color in colors):
        return 0.92
    return 0.76 if len(set(colors)) == 2 else 0.4


def style_coherence(items):
    styles = [item.get("style") for item in items if item.get("style")]
    if len(styles) < len(items):
        return 0.5
    scores = []
    for index, style in enumerate(styles):
        for other in styles[index + 1:]:
            scores.append(1.0 if style == other else STYLE_COMPATIBILITY.get(
                (style, other), STYLE_COMPATIBILITY.get((other, style), 0.62)
            ))
    return average(scores) if scores else 0.75


def style_fit(items, target_styles):
    coherence = style_coherence(items)
    if not target_styles:
        return coherence
    matches = [
        max(
            1.0 if item.get("style") == target else STYLE_COMPATIBILITY.get(
                (item.get("style"), target), STYLE_COMPATIBILITY.get((target, item.get("style")), 0.4)
            )
            for target in target_styles
        )
        for item in items
    ]
    return 0.65 * average(matches) + 0.35 * coherence


def preference_fit(items, memories):
    score = 0.5
    colors = [item.get("color") for item in items]
    styles = {item.get("style") for item in items}
    for memory in memories:
        key = memory.get("memory_key", "")
        if key == "outfit.color.all_black" and colors and all(color == "黑色系" for color in colors):
            score = 0.0 if memory.get("memory_type") == "avoidance" else 1.0
        if key == "outfit.style.minimal" and "简约" in styles:
            score = max(score, 0.95)
    return score


def saved_prior(items, outfits):
    ids = {item["id"] for item in items}
    best = 0.0
    for outfit in outfits:
        saved_ids = {item["id"] for item in outfit.get("clothes", [])}
        if ids == saved_ids:
            return 1.0
        if len(ids & saved_ids) >= 2:
            best = max(best, 0.7)
    return best


def diversify_mmr(candidates, limit):
    selected = []
    remaining = list(candidates)
    while remaining and len(selected) < limit:
        def mmr(candidate):
            ids = {item["id"] for item in candidate["clothes"]}
            overlap = max((jaccard(ids, {item["id"] for item in chosen["clothes"]}) for chosen in selected), default=0)
            return candidate["score"] - 0.15 * overlap

        best = max(remaining, key=mmr)
        selected.append(best)
        remaining.remove(best)
    return selected


def explain_candidate(items, parts, seasons, occasions):
    names = " + ".join(item["name"] for item in items)
    highlights = []
    if occasions:
        highlights.append("场合标签匹配" if parts["occasion"] >= 0.7 else "部分场合标签未记录")
    if seasons:
        highlights.append("季节适配" if parts["season_weather"] >= 0.7 else "季节信息不完整")
    if parts["color"] >= 0.8:
        highlights.append("颜色协调")
    if parts["style"] >= 0.75:
        highlights.append("风格统一")
    return f"{names}：{'、'.join(highlights) if highlights else '结构完整，适合日常组合'}。"


def missing_caveats(items):
    missing = sorted({field for item in items for field in ("season", "occasion", "color", "style") if not item.get(field)})
    return [f"{'、'.join(missing)}属性未完整记录"] if missing else []


def outfit_name(occasions):
    if "正式职业场合" in occasions:
        return "正式职业穿搭"
    if "商务交流场合" in occasions:
        return "通勤穿搭"
    if "日常社交场合" in occasions:
        return "社交穿搭"
    return "日常穿搭"


def average(values):
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def jaccard(left, right):
    return len(left & right) / len(left | right) if left or right else 0.0
