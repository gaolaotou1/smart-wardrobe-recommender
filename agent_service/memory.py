def review_memory_operations(text: str):
    normalized = text.strip()
    if any(word in normalized for word in ("忘掉", "删除记忆", "不要记得")):
        return []
    if any(word in normalized for word in ("不要", "不喜欢", "避免")):
        if "全黑" in normalized or "一身黑" in normalized:
            return [
                {
                    "memory_type": "avoidance",
                    "memory_key": "outfit.color.all_black",
                    "content": "用户不喜欢全黑搭配",
                    "structured_value": {"pattern": "all_black", "preference": "avoid"},
                    "confidence": 0.98,
                }
            ]
    if any(word in normalized for word in ("喜欢", "偏好", "更爱")):
        if "简约" in normalized:
            return [
                {
                    "memory_type": "preference",
                    "memory_key": "outfit.style.minimal",
                    "content": "用户偏好简约风格",
                    "structured_value": {"style": "简约", "preference": "prefer"},
                    "confidence": 0.95,
                }
            ]
        if "全黑" in normalized or "一身黑" in normalized:
            return [
                {
                    "memory_type": "preference",
                    "memory_key": "outfit.color.all_black",
                    "content": "用户喜欢全黑搭配",
                    "structured_value": {"pattern": "all_black", "preference": "prefer"},
                    "confidence": 0.95,
                }
            ]
    return []
