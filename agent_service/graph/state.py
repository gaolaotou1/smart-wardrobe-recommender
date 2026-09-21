from typing import TypedDict


class AgentState(TypedDict, total=False):
    run_id: str
    session_id: str
    thread_id: str
    user_id: int
    request_id: str
    now_iso: str
    user_input: str
    user_message_id: int
    selected_clothes_ids: list[int]
    attachments: list[dict]
    recent_messages: list[dict]
    session_summary: dict
    relevant_memories: list[dict]
    active_slots: dict
    referenced_clothes_ids: list[int]
    referenced_outfit_ids: list[int]
    route: dict
    plan: dict
    task_results: dict[str, dict]
    evidence_report: dict
    recommendation_candidates: list[dict]
    pending_action: dict | None
    action_decision: dict | None
    answer_draft: dict | None
    final_answer: dict | None
    replan_count: int
    tool_call_count: int
    repair_count: int
    model_usage: dict
    seen_tool_fingerprints: list[str]
    warnings: list[str]
    failure: dict | None
    referenced_outfit: dict | None
