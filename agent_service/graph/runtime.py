from datetime import datetime
import time

from langgraph.graph import END, START, StateGraph
from langgraph.config import var_child_runnable_config
from langgraph.types import interrupt

from agent_service.chat.schemas import AgentAnswer, RouteDecision
from agent_service.logging import get_logger
from .routing import make_execution_plan
from .state import AgentState


logger = get_logger()


def traced(stage, node, *, with_config=False):
    async def run(state, config=None):
        fields = {
            "stage": stage,
            "run_id": state.get("run_id"),
            "session_id": state.get("session_id"),
        }
        started = time.perf_counter()
        logger.info("agent_stage_started", **fields)
        try:
            result = await node(state, config) if with_config else await node(state)
        except Exception as exc:
            status = "paused" if "Interrupt" in exc.__class__.__name__ else "failed"
            logger.warning(
                "agent_stage_finished",
                **fields,
                status=status,
                error_type=None if status == "paused" else exc.__class__.__name__,
                latency_ms=round((time.perf_counter() - started) * 1000),
            )
            raise
        logger.info(
            "agent_stage_finished",
            **fields,
            status="succeeded",
            latency_ms=round((time.perf_counter() - started) * 1000),
            **stage_details(stage, result),
        )
        return result

    return run


def stage_details(stage, result):
    if stage == "load_context":
        return {
            "history_count": len(result.get("recent_messages", [])),
            "memory_count": len(result.get("relevant_memories", [])),
        }
    if stage == "resolve_reference":
        return {"reference_count": len(result.get("referenced_clothes_ids", []))}
    if stage == "route_intent":
        route = result.get("route", {})
        return {
            "route": route.get("primary_route"),
            "task_count": len(route.get("tasks", [])),
            "needs_clarification": route.get("needs_clarification", False),
            "warning_count": len(result.get("warnings", [])),
        }
    if stage == "make_plan":
        steps = result.get("plan", {}).get("steps", [])
        return {"tool_path": [step.get("action") for step in steps]}
    if stage in {"execute_ready_tasks", "validate_answer", "commit_outfit_action"}:
        answer = result.get("answer_draft") or result.get("final_answer") or {}
        return {
            "route": answer.get("route"),
            "partial": answer.get("partial", False),
            "evidence_count": len(answer.get("evidence_ids", [])),
            "card_count": len(answer.get("cards", [])),
            "outfit_count": len(answer.get("outfits", [])),
        }
    if stage == "evidence_gate":
        report = result.get("evidence_report", {})
        return {
            "evidence_sufficient": report.get("sufficient", False),
            "evidence_count": len(report.get("evidence_ids", [])),
            "waiting_user": report.get("waiting_user", False),
        }
    if stage == "persist_turn":
        return {"persisted": True}
    return {}


def build_runtime_graph(agent, checkpointer=None):
    async def ingress_guard(state):
        if not state.get("user_id"):
            raise PermissionError("未认证的 Agent 请求")
        if len(state.get("user_input", "")) > 8_000:
            raise ValueError("输入超过 8000 字符")
        if len(state.get("attachments", [])) > 1:
            raise ValueError("V1 每轮最多允许 1 张附图")
        return {"now_iso": datetime.now().astimezone().isoformat()}

    async def load_context(state):
        messages, memories, summary = agent.load_context(
            state["user_id"], state["session_id"], state["user_input"],
        )
        return {"recent_messages": messages, "relevant_memories": memories, "session_summary": summary}

    async def resolve_reference(state):
        clothes_ids, outfit = agent.resolve_references(state)
        return {"referenced_clothes_ids": clothes_ids, "referenced_outfit": outfit}

    async def route_intent(state):
        decision, warnings, usage = await agent.route_decision(state)
        agent.store.update_run_route(
            state["run_id"], decision.primary_route,
            agent.config.text_model_provider, agent.text_model.model,
        )
        return {
            "route": decision.model_dump(mode="json"),
            "active_slots": decision.slots.model_dump(mode="json"),
            "warnings": [*state.get("warnings", []), *warnings],
            "model_usage": usage,
        }

    async def clarify(state):
        decision = RouteDecision.model_validate(state["route"])
        answer = agent.answer(
            state["session_id"], decision.primary_route,
            decision.clarification_question or "请补充一个关键条件。",
            warnings=state.get("warnings", []),
        )
        return {"answer_draft": answer, "evidence_report": {"sufficient": False, "needs_user": True}}

    async def make_plan(state):
        plan = make_execution_plan(RouteDecision.model_validate(state["route"]))
        return {"plan": plan.model_dump(mode="json")}

    async def execute_ready_tasks(state):
        result = await agent.execute(state)
        if state.get("warnings"):
            result["warnings"] = list(dict.fromkeys([*result.get("warnings", []), *state["warnings"]]))
        return {
            "answer_draft": result,
            "tool_call_count": min(len(state.get("plan", {}).get("steps", [])), agent.config.max_tool_calls),
            "model_usage": state.get("model_usage", {}),
        }

    async def evidence_gate(state):
        answer = state["answer_draft"]
        return {"evidence_report": {
            "sufficient": not answer.get("partial", False),
            "waiting_user": bool(answer.get("pending_action")),
            "evidence_ids": answer.get("evidence_ids", []),
        }}

    async def compose_answer(state):
        return {"answer_draft": state["answer_draft"]}

    async def validate_answer(state):
        validated = AgentAnswer.model_validate(state["answer_draft"]).model_dump(mode="json")
        return {"final_answer": validated}

    async def persist_turn(state):
        if agent.store.run_is_cancelled(state["run_id"]):
            return {}
        agent.store.record_tool_calls(
            state["run_id"], state["user_id"],
            state.get("plan", {}).get("steps", []), state["final_answer"],
        )
        agent.persist_result(state, state["final_answer"])
        return {}

    async def confirm_action(state, config):
        token = var_child_runnable_config.set(config)
        try:
            decision = interrupt(state["final_answer"]["pending_action"])
            return {"action_decision": decision}
        finally:
            var_child_runnable_config.reset(token)

    async def commit_outfit_action(state):
        decision = state["action_decision"]
        if decision["decision"] == "reject":
            result = agent.reject_pending_action(
                state["user_id"], state["session_id"], decision["action_id"], decision.get("client_decision_id"),
            )
        else:
            result = agent.commit_pending_action(
                state["user_id"], state["session_id"], decision["action_id"],
                decision.get("expected_payload_hash"), decision.get("client_decision_id"),
            )
        agent.store.record_tool_call(
            state["run_id"], state["user_id"], "commit_outfit_change",
            {"action_id": decision["action_id"], "decision": decision["decision"]},
            result.get("evidence_ids", [None])[0] if result.get("evidence_ids") else None,
            len(result.get("outfits", [])),
        )
        return {"answer_draft": result, "action_decision": None}

    async def enqueue_memory_review(state):
        agent.enqueue_memory_review(state)
        return {}

    builder = StateGraph(AgentState)
    for name, node in (
        ("ingress_guard", ingress_guard),
        ("load_context", load_context),
        ("resolve_reference", resolve_reference),
        ("route_intent", route_intent),
        ("clarify", clarify),
        ("make_plan", make_plan),
        ("execute_ready_tasks", execute_ready_tasks),
        ("evidence_gate", evidence_gate),
        ("compose_answer", compose_answer),
        ("validate_answer", validate_answer),
        ("persist_turn", persist_turn),
        ("confirm_action", confirm_action),
        ("commit_outfit_action", commit_outfit_action),
        ("enqueue_memory_review", enqueue_memory_review),
    ):
        builder.add_node(name, traced(name, node, with_config=name == "confirm_action"))

    builder.add_edge(START, "ingress_guard")
    builder.add_edge("ingress_guard", "load_context")
    builder.add_edge("load_context", "resolve_reference")
    builder.add_edge("resolve_reference", "route_intent")
    builder.add_conditional_edges(
        "route_intent",
        lambda state: "clarify" if state["route"].get("needs_clarification") else "make_plan",
        {"clarify": "clarify", "make_plan": "make_plan"},
    )
    builder.add_edge("clarify", "validate_answer")
    builder.add_edge("make_plan", "execute_ready_tasks")
    builder.add_edge("execute_ready_tasks", "evidence_gate")
    builder.add_edge("evidence_gate", "compose_answer")
    builder.add_edge("compose_answer", "validate_answer")
    builder.add_edge("validate_answer", "persist_turn")
    builder.add_conditional_edges(
        "persist_turn",
        lambda state: "confirm_action" if state["final_answer"].get("pending_action") else "enqueue_memory_review",
        {"confirm_action": "confirm_action", "enqueue_memory_review": "enqueue_memory_review"},
    )
    builder.add_edge("confirm_action", "commit_outfit_action")
    builder.add_edge("commit_outfit_action", "validate_answer")
    builder.add_edge("enqueue_memory_review", END)
    return builder.compile(checkpointer=checkpointer)
