import asyncio
import re
import time
import uuid

import httpx
from pydantic import BaseModel, Field, ValidationError
from langgraph.types import Command

from agent_service.attachments import LocalAttachmentStore
from agent_service.config import load_agent_config
from agent_service.graph.routing import deterministic_route, make_execution_plan, route_with_model
from agent_service.memory import review_memory_operations
from agent_service.models.ark_text import ArkTextModelPort
from agent_service.models.deepseek import DeepSeekModelPort
from agent_service.models.doubao_vision import DoubaoVisionPort
from agent_service.models.weather import OpenMeteoWeatherPort
from agent_service.logging import get_logger
from agent_service.persistence.store import AgentStore
from agent_service.query.repository import WardrobeRepository
from agent_service.query.semantic import detect_colors
from agent_service.query.spec import QueryFilter, QuerySpec, SavedOutfitQuery, spec_from_text
from agent_service.recommendation.engine import recommend_outfits
from .schemas import AgentAnswer, RouteDecision
from .validator import validate_agent_answer


class ShortAnswer(BaseModel):
    answer: str


class CandidateReview(BaseModel):
    selected_candidate_ids: list[str] = Field(default_factory=list, max_length=5)
    reasons: dict[str, str] = Field(default_factory=dict)
    need_more_evidence: bool = False
    missing_evidence: list[str] = Field(default_factory=list)


logger = get_logger()


class WardrobeAgent:
    def __init__(self, connect, store: AgentStore | None = None, checkpointer=None, read_connect=None):
        self.config = load_agent_config()
        self.repository = WardrobeRepository(read_connect or connect)
        self.store = store or AgentStore(connect)
        self.text_model = self._build_text_model()
        self.vision_model = DoubaoVisionPort()
        self.uploads = LocalAttachmentStore()
        self.weather = OpenMeteoWeatherPort()
        self.graph = self._build_graph(checkpointer)

    def _build_text_model(self):
        if self.config.text_model_provider == "ark":
            return ArkTextModelPort()
        return DeepSeekModelPort()

    def _build_graph(self, checkpointer):
        from agent_service.graph.runtime import build_runtime_graph

        return build_runtime_graph(self, checkpointer)

    def route(self, text: str) -> str:
        """Deterministic fallback and stable unit-test seam."""
        return deterministic_route(text).primary_route

    async def chat(self, user_id: int, payload: dict):
        text = (payload.get("text") or payload.get("message") or payload.get("question") or "").strip()
        attachments = normalize_attachments(payload)
        if not text:
            return self.answer(
                payload.get("session_id") or "",
                "fashion_qa",
                "你可以直接问：我有几件冬天外套，或帮我搭一套通勤穿搭。",
            )

        session_id = self.store.ensure_session(user_id, payload.get("session_id") or payload.get("thread_id"))
        client_message_id = payload.get("client_message_id") or str(uuid.uuid4())
        cached = self.store.get_message_by_client_id(user_id, session_id, client_message_id)
        if cached:
            return cached

        pending = self.store.latest_pending_action(user_id, session_id)
        if pending and (self.is_confirmation(text) or self.is_rejection(text)):
            self.store.add_message(
                user_id=user_id, session_id=session_id, role="user", content=text,
                client_message_id=client_message_id, attachments=attachments,
            )
            return await self.resume_pending_action(
                user_id, session_id, pending["id"],
                "reject" if self.is_rejection(text) else "approve",
                pending["payload_hash"],
            )

        message_id = self.store.add_message(
            user_id=user_id,
            session_id=session_id,
            role="user",
            content=text,
            client_message_id=client_message_id,
            attachments=attachments,
        )
        run_id = self.store.create_run(user_id, session_id, message_id, None)
        started = time.perf_counter()
        logger.info(
            "agent_run_started",
            run_id=run_id,
            session_id=session_id,
            user_id=user_id,
            input_chars=len(text),
            attachment_count=len(attachments),
        )
        initial = {
            "run_id": run_id,
            "thread_id": session_id,
            "session_id": session_id,
            "user_id": user_id,
            "request_id": client_message_id,
            "user_message_id": message_id,
            "user_input": text,
            "attachments": attachments,
            "selected_clothes_ids": unique_ids(payload.get("selected_clothes_ids") or [])[:20],
            "replan_count": 0,
            "tool_call_count": 0,
            "repair_count": 0,
            "model_usage": empty_usage(),
            "warnings": [],
            "task_results": {},
            "seen_tool_fingerprints": [],
        }
        try:
            state = await asyncio.wait_for(
                self.graph.ainvoke(initial, config={"configurable": {"thread_id": session_id}}),
                timeout=self.config.run_timeout_seconds,
            )
        except asyncio.TimeoutError:
            result = self.answer(
                session_id, deterministic_route(text, attachments).primary_route,
                "本轮已达到时间上限，我已停止继续执行，没有在后台写入穿搭。",
                partial=True, warnings=["MODEL_TIMEOUT"],
            )
            self.store.add_message(
                user_id=user_id, session_id=session_id, role="assistant",
                content=result["answer"], structured_content=result,
            )
            self.store.finish_run(run_id, "partial", error_code="MODEL_TIMEOUT")
            logger.warning(
                "agent_run_finished",
                run_id=run_id,
                session_id=session_id,
                status="partial",
                error_type="MODEL_TIMEOUT",
                latency_ms=round((time.perf_counter() - started) * 1000),
            )
            return result
        except Exception as exc:
            self.store.finish_run(run_id, "failed", error_code=exc.__class__.__name__)
            logger.exception(
                "agent_run_finished",
                run_id=run_id,
                session_id=session_id,
                status="failed",
                error_type=exc.__class__.__name__,
                latency_ms=round((time.perf_counter() - started) * 1000),
            )
            raise
        answer = state["final_answer"]
        logger.info(
            "agent_run_finished",
            run_id=run_id,
            session_id=session_id,
            status="waiting_user" if answer.get("pending_action") else "partial" if answer.get("partial") else "succeeded",
            route=answer.get("route"),
            evidence_count=len(answer.get("evidence_ids", [])),
            latency_ms=round((time.perf_counter() - started) * 1000),
        )
        return answer

    async def resume_pending_action(self, user_id, session_id, action_id, decision, expected_hash, client_decision_id=None):
        action = self.store.get_pending_action(user_id, session_id, action_id)
        if not action:
            return self.answer(session_id, "outfit_management", "待确认操作不存在。")
        if action["status"] == "executed":
            return self.commit_pending_action(user_id, session_id, action_id, expected_hash)
        if action["status"] == "rejected":
            return self.answer(session_id, "outfit_management", "该操作已取消，没有写入数据库。")
        state = await self.graph.ainvoke(
            Command(resume={
                "action_id": action_id,
                "decision": decision,
                "expected_payload_hash": expected_hash,
                "client_decision_id": client_decision_id,
            }),
            config={"configurable": {"thread_id": session_id}},
        )
        return state["final_answer"]

    async def route_decision(self, state: dict):
        text = state["user_input"]
        if state.get("attachments"):
            return deterministic_route(text, state["attachments"]), [], empty_usage()
        if is_clothes_mutation(text):
            return deterministic_route("我的衣橱有哪些衣服"), [], empty_usage()
        if is_outfit_management_request(text):
            return deterministic_route(text), [], empty_usage()
        if self.is_confirmation(text) or self.is_rejection(text):
            return deterministic_route("保存穿搭"), [], empty_usage()
        if not model_ready(self.config):
            return deterministic_route(text, state.get("attachments")), ["文本模型未配置，已使用受限规则路由"], empty_usage()
        try:
            decision, results = await route_with_model(
                self.text_model,
                text,
                compact_messages_without_current(state.get("recent_messages", []), text),
                state.get("attachments", []),
            )
            return decision, [], usage_from_results(results)
        except Exception as exc:
            warning = f"模型路由不可用，已安全降级（{exc.__class__.__name__}）"
            return deterministic_route(text, state.get("attachments")), [warning], empty_usage()

    def load_context(self, user_id: int, session_id: str, text: str):
        messages = self.store.list_messages(user_id, session_id, 12)
        memories = self.store.list_memories(user_id, text=text, limit=8) if self.config.long_term_memory_enabled else []
        session = self.store.session_context(user_id, session_id)
        return messages, memories, session["summary"]

    def resolve_references(self, state: dict):
        text = state["user_input"]
        ids = unique_ids(re.findall(r"#?(\d+)", text))
        previous_outfits = []
        for message in reversed(state.get("recent_messages", [])):
            structured = message.get("structured_content") or {}
            if structured.get("outfits"):
                previous_outfits = structured["outfits"]
                break
        ordinal = extract_ordinal(text)
        referenced = previous_outfits[ordinal - 1] if ordinal and ordinal <= len(previous_outfits) else None
        refining = any(word in text for word in ("更", "换", "调整", "不变"))
        if referenced and not refining:
            ids.extend(item["id"] for item in referenced.get("clothes", []))
        return unique_ids(ids), referenced

    async def execute(self, state: dict) -> dict:
        text = state["user_input"]
        session_id = state["session_id"]
        if is_clothes_mutation(text):
            return self.answer(
                session_id, "wardrobe_query",
                "问答 Agent 对衣物只读，不能直接新增、修改或删除衣物。请在虚拟衣柜中手动操作。",
            )
        if self.is_confirmation(text):
            return self.commit_pending_action(state["user_id"], session_id)
        if self.is_rejection(text):
            return self.reject_pending_action(state["user_id"], session_id)

        decision = RouteDecision.model_validate(state["route"])
        if decision.needs_clarification:
            return self.answer(session_id, decision.primary_route, decision.clarification_question or "请补充关键条件。")

        results = []
        for task in topological_tasks(decision.tasks):
            objective = task.objective or text
            if task.route == "wardrobe_query":
                spec = decision.query_spec if len(decision.tasks) == 1 and decision.query_spec else spec_from_text(objective)
                results.append(self.handle_wardrobe_query(state["user_id"], session_id, objective, spec))
            elif task.route == "outfit_recommendation":
                results.append(await self.handle_recommendation(state, objective, decision))
            elif task.route == "image_analysis":
                results.append(await self.handle_image_analysis(state, objective))
            elif task.route == "outfit_management":
                results.append(self.handle_outfit_management(state, objective))
            else:
                results.append(await self.handle_fashion_qa(state, objective))
        return merge_answers(session_id, decision.primary_route, results)

    def handle_wardrobe_query(self, user_id, session_id, text, spec: QuerySpec):
        evidence = with_evidence(self.repository.search_wardrobe(user_id, spec), "mysql")
        if spec.aggregates:
            groups = evidence["data"].get("groups", [])
            if groups:
                detail = "、".join(f"{item['group_value']} {item['value']} 件" for item in groups[:10])
                message = f"根据当前衣橱数据，{detail}。"
            else:
                message = f"根据当前衣橱数据，匹配条件的衣物有 {evidence['data']['total']} 件。"
            fact = {"type": "count", "label": "匹配衣物", "value": evidence["data"]["total"], "evidence_id": evidence["evidence_id"]}
            return self.answer(session_id, "wardrobe_query", message, facts=[fact], evidence=[evidence])

        items = evidence["data"]["items"]
        if not items:
            return self.answer(session_id, "wardrobe_query", "我查了你的衣橱，暂时没有找到匹配的衣物。", evidence=[evidence])
        names = "、".join(f"#{item['id']} {item['name']}" for item in items[:8])
        suffix = "，还有更多结果" if evidence["data"].get("has_more") else ""
        return self.answer(
            session_id,
            "wardrobe_query",
            f"我在你的衣橱里找到 {len(items)} 件：{names}{suffix}。",
            cards=items,
            evidence=[evidence],
        )

    async def handle_recommendation(self, state, text, decision):
        user_id = state["user_id"]
        session_id = state["session_id"]
        if not self.config.recommendation_v2_enabled:
            return self.answer(session_id, "outfit_recommendation", "穿搭推荐 V2 当前已关闭。", partial=True)
        clothes = self.repository.list_all_clothes(user_id)
        if not clothes:
            return self.answer(session_id, "outfit_recommendation", "你的衣橱里还没有衣物，先添加衣物后我就能搭配了。")
        seed_ids = unique_ids([
            *state.get("selected_clothes_ids", []),
            *state.get("referenced_clothes_ids", []),
            *decision.slots.seed_clothes_ids,
        ])
        saved = self.repository.search_saved_outfits(user_id)
        if state.get("referenced_outfit"):
            saved = [state["referenced_outfit"], *saved]
        intent_text = state["user_input"]
        weather_evidence = None
        assumptions = []
        warnings = []
        if decision.slots.weather_needed:
            if self.config.weather_enabled and decision.slots.location:
                try:
                    weather = await self.weather.current(decision.slots.location)
                    weather_evidence = with_evidence(weather.to_dict(), "open_meteo")
                    season_text = {
                        "winter": "冬天", "summer": "夏天", "spring_and_autumn": "春秋",
                    }[weather.suggested_season]
                    intent_text += f" {season_text}"
                    assumptions.append(
                        f"{weather.location} {weather.observed_at} 体感 {weather.apparent_temperature_c:g}℃，"
                        f"降水 {weather.precipitation_mm:g} mm"
                    )
                except (httpx.HTTPError, KeyError, ValueError) as exc:
                    warnings.append(f"天气服务不可用，已退化为季节推荐（{exc.__class__.__name__}）")
            else:
                assumptions.append("未使用实时天气")
        required_match_ids = []
        if len(decision.tasks) > 1 and decision.slots.garment_roles:
            required_match_ids = [
                item["id"] for item in clothes
                if item.get("garment_role") in decision.slots.garment_roles
            ]
        candidates = recommend_outfits(
            clothes,
            intent_text,
            seed_ids=seed_ids,
            limit=decision.slots.result_limit,
            memories=state.get("relevant_memories", []),
            saved_outfits=saved,
            required_match_ids=required_match_ids,
        )
        if not candidates:
            message = "找到了条件相关的衣物，但当前衣橱缺少能组成完整穿搭的互补角色。" if seed_ids else "当前衣橱还凑不出满足条件的完整穿搭。"
            return self.answer(session_id, "outfit_recommendation", message, partial=True)

        candidates = await self.review_candidates(state, text, candidates)
        lines = [f"我基于你的真实衣橱生成了 {len(candidates)} 套候选："]
        for index, candidate in enumerate(candidates, 1):
            names = "、".join(f"#{item['id']} {item['name']}" for item in candidate["clothes"])
            lines.append(f"{index}. {candidate['name']}：{names}。{candidate['reason']}")
        lines.append("要保存时可以说“保存第一套为周一通勤”。")
        evidence = with_evidence({"candidates": candidates}, "rules")
        evidences = [weather_evidence, evidence] if weather_evidence else [evidence]
        return self.answer(
            session_id, "outfit_recommendation", "\n".join(lines),
            outfits=candidates, evidence=evidences, assumptions=assumptions, warnings=warnings,
        )

    async def review_candidates(self, state, text, candidates):
        if not model_ready(self.config):
            return candidates
        compact = [{
            "candidate_id": item["candidate_id"],
            "clothes": [{"id": c["id"], "name": c["name"], "role": c["garment_role"]} for c in item["clothes"]],
            "score_breakdown": item["score_breakdown"],
            "caveats": item["caveats"],
        } for item in candidates[:10]]
        try:
            review = await self.structured_validated(
                state,
                purpose="candidate_review",
                system="只能从候选 candidate_id 中选择，不得新造衣物。硬约束不可改写。",
                messages=[{"role": "user", "content": f"需求：{text}\n候选：{compact}"}],
                schema_type=CandidateReview,
            )
        except Exception:
            return candidates
        by_id = {item["candidate_id"]: item for item in candidates}
        selected = [by_id[item_id] for item_id in review.selected_candidate_ids if item_id in by_id]
        for item in selected:
            item["reason"] = review.reasons.get(item["candidate_id"], item["reason"])
        return selected or candidates

    async def handle_image_analysis(self, state, text):
        session_id = state["session_id"]
        attachments = state.get("attachments", [])
        if not attachments:
            return self.answer(session_id, "image_analysis", "请先附上 1 张需要分析的衣物图片。")
        if not self.config.image_analysis_enabled:
            return self.answer(session_id, "image_analysis", "当前未启用图片分析功能。")
        attachment = attachments[0]
        source = attachment.get("url") or self.uploads.data_url(state["user_id"], attachment["upload_id"])
        analysis = await self.vision_model.analyze(source, text)
        data = analysis.model_dump()
        evidence = with_evidence(data, "doubao")
        evidences = [evidence]
        cards = []
        message = f"这件看起来是{data['colors'][0] if data['colors'] else ''}{data['sub_category'] or data['category']}，风格偏{'、'.join(data['style']) or '未确定'}。"
        if data["uncertain_fields"]:
            message += f" { '、'.join(data['uncertain_fields']) } 只是图像推测，需要你确认。"
        if any(word in text for word in ("类似", "我有", "衣橱")):
            filters = []
            if data["semantic_role"] != "unknown":
                filters.append(QueryFilter(field="garment_role", op="eq", value=data["semantic_role"]))
            if data["colors"]:
                colors = detect_colors(" ".join(data["colors"])) or data["colors"]
                filters.append(QueryFilter(field="color", op="in", value=colors[:3]))
            wardrobe = with_evidence(
                self.repository.search_wardrobe(state["user_id"], QuerySpec(filters=filters, limit=8)),
                "mysql",
            )
            evidences.append(wardrobe)
            cards = wardrobe["data"]["items"]
            message += f" 你的衣橱里找到 {wardrobe['data']['total']} 件属性相近的衣物。"
        return self.answer(
            session_id, "image_analysis", message,
            analysis=data, cards=cards, evidence=evidences,
        )

    async def handle_fashion_qa(self, state, text):
        session_id = state["session_id"]
        if any(word in text for word in ("忘掉", "删除记忆", "不要记得")):
            if any(word in text for word in ("全部", "所有", "一切")):
                changed = self.store.delete_all_memories(state["user_id"])
            else:
                memories = self.store.list_memories(state["user_id"])
                targets = [
                    item for item in memories
                    if ("全黑" in text and "all_black" in item["memory_key"])
                    or ("简约" in text and "minimal" in item["memory_key"])
                    or item["content"] in text
                ]
                changed = sum(self.store.delete_memory(state["user_id"], item["id"]) for item in targets)
            return self.answer(
                session_id, "fashion_qa",
                f"已忘掉 {changed} 条相关记忆。" if changed else "没有找到与这句话对应的长期记忆。",
            )
        if "你记得我什么" in text:
            memories = state.get("relevant_memories") or self.store.list_memories(state["user_id"])
            message = "我目前没有保存长期穿搭记忆。" if not memories else "我记得：\n" + "\n".join(f"- {item['content']}" for item in memories)
            return self.answer(session_id, "fashion_qa", message)
        if not model_ready(self.config):
            return self.answer(session_id, "fashion_qa", simple_fashion_answer(text), warnings=["文本模型未配置，已使用本地知识模板"])
        try:
            result = await self.structured_validated(
                state,
                purpose="fashion_qa",
                system="回答通用服饰知识。不得声称知道用户衣橱中未经工具查询的事实。简洁、可执行。",
                messages=[{"role": "user", "content": text}],
                schema_type=ShortAnswer,
            )
            return self.answer(session_id, "fashion_qa", result.answer)
        except Exception as exc:
            return self.answer(
                session_id, "fashion_qa", simple_fashion_answer(text),
                warnings=[f"文本模型不可用，已使用本地知识模板（{exc.__class__.__name__}）"],
            )

    async def structured_validated(self, state, *, purpose, system, messages, schema_type):
        result = await self.text_model.structured(
            purpose=purpose,
            system=system,
            messages=messages,
            schema=schema_type.model_json_schema(),
        )
        add_usage(state, result)
        try:
            return schema_type.model_validate(result.content)
        except ValidationError as error:
            repair = await self.text_model.structured(
                purpose=f"{purpose}_repair",
                system="只修复 JSON 结构，不增加新事实。",
                messages=[{
                    "role": "user",
                    "content": f"原 JSON：{result.raw_text[:4_000]}\n校验错误：{error.errors(include_url=False)}",
                }],
                schema=schema_type.model_json_schema(),
            )
            add_usage(state, repair)
            return schema_type.model_validate(repair.content)

    def handle_outfit_management(self, state, text):
        user_id = state["user_id"]
        session_id = state["session_id"]
        if any(word in text for word in ("已保存", "我的穿搭", "查看穿搭")):
            outfits = self.repository.search_saved_outfits(user_id)
            message = "你目前还没有保存过穿搭。" if not outfits else "你已保存的穿搭有：\n" + "\n".join(
                f"- #{item['id']} {item['name']}" for item in outfits[:8]
            )
            evidence = with_evidence({"outfits": outfits}, "mysql")
            return self.answer(session_id, "outfit_management", message, outfits=outfits, evidence=[evidence])
        if not self.config.outfit_mutations_enabled:
            return self.answer(session_id, "outfit_management", "穿搭写操作尚未启用。")

        operation = "delete" if "删除" in text else "update" if any(word in text for word in ("修改", "重命名")) else "create"
        if operation == "create":
            candidate = state.get("referenced_outfit")
            if not candidate:
                return self.answer(session_id, "outfit_management", "我没有找到可保存的上一轮推荐。请先让我推荐穿搭。")
            name = extract_save_name(text) or candidate["name"]
            payload = {
                "kind": "create_outfit", "operation": "create", "name": name,
                "description": candidate.get("reason", ""),
                "clothes_ids": [item["id"] for item in candidate["clothes"]],
            }
            summary = f"保存穿搭“{name}”，包含：" + "、".join(f"#{item['id']} {item['name']}" for item in candidate["clothes"])
        else:
            ids = unique_ids(re.findall(r"#?(\d+)", text))
            if not ids:
                return self.answer(session_id, "outfit_management", "请明确说出要操作的穿搭 ID。")
            outfits = self.repository.search_saved_outfits(user_id, SavedOutfitQuery(outfit_ids=[ids[0]], limit=1))
            if not outfits:
                return self.answer(session_id, "outfit_management", "没有找到该穿搭。")
            target = outfits[0]
            if operation == "delete":
                payload = {
                    "kind": "delete_outfit", "operation": "delete",
                    "target_outfit_id": target["id"], "expected_updated_at": target["updated_at"],
                }
                summary = f"删除穿搭 #{target['id']} “{target['name']}”，包含：" + "、".join(item["name"] for item in target["clothes"])
            else:
                name = extract_rename(text) or target["name"]
                payload = {
                    "kind": "update_outfit", "operation": "update", "target_outfit_id": target["id"],
                    "name": name, "description": target.get("description", ""),
                    "clothes_ids": [item["id"] for item in target["clothes"]],
                    "expected_updated_at": target["updated_at"],
                }
                summary = f"将穿搭 #{target['id']} 重命名为“{name}”"

        action = self.store.create_pending_action(user_id=user_id, session_id=session_id, payload=payload, human_summary=summary)
        return self.answer(
            session_id, "outfit_management",
            f"准备{summary}。这一步尚未写入数据库，请确认或取消。",
            pending_action=action,
        )

    def commit_pending_action(self, user_id, session_id, action_id=None, expected_hash=None, client_decision_id=None):
        action = self.store.get_pending_action(user_id, session_id, action_id) if action_id else self.store.latest_pending_action(user_id, session_id)
        if not action:
            return self.answer(session_id, "outfit_management", "当前没有唯一等待确认的穿搭操作。")
        if action["status"] == "executed":
            from agent_service.persistence.store import load_json

            result = load_json(action.get("result_json"))
            evidence = with_evidence({"outfits": [result]}, "mysql")
            return self.answer(
                session_id, "outfit_management",
                f"该操作已执行：穿搭 #{result['id']} “{result['name']}”。",
                outfits=[] if result.get("deleted") else [result], evidence=[evidence],
            )
        result = self.store.execute_outfit_action(
            user_id, session_id, action["id"], expected_hash or action["payload_hash"], client_decision_id,
        )
        message = f"已删除穿搭“{result['name']}”。" if result.get("deleted") else f"已保存穿搭“{result['name']}”，穿搭 ID 是 #{result['id']}。"
        evidence = with_evidence({"outfits": [result]}, "mysql")
        return self.answer(
            session_id, "outfit_management", message,
            outfits=[] if result.get("deleted") else [result], evidence=[evidence],
        )

    def reject_pending_action(self, user_id, session_id, action_id=None, client_decision_id=None):
        action = self.store.get_pending_action(user_id, session_id, action_id) if action_id else self.store.latest_pending_action(user_id, session_id)
        if not action:
            return self.answer(session_id, "outfit_management", "当前没有等待取消的穿搭操作。")
        self.store.reject_pending_action(user_id, session_id, action["id"], client_decision_id)
        return self.answer(session_id, "outfit_management", "已取消本次穿搭操作，没有写入数据库。")

    def answer(self, session_id, route, message, *, cards=None, outfits=None, facts=None, assumptions=None,
               warnings=None, pending_action=None, analysis=None, partial=False, evidence=None):
        evidence = evidence or []
        images = []
        for collection in [cards or [], *[outfit.get("clothes", []) for outfit in outfits or []]]:
            for item in collection:
                if item.get("image_url") and item["image_url"] not in images:
                    images.append(item["image_url"])
        payload = {
            "session_id": session_id,
            "answer": message,
            "message": message,
            "route": route,
            "completed_tasks": [route],
            "partial": partial,
            "cards": cards or [],
            "outfits": outfits or [],
            "analysis": analysis,
            "facts": facts or [],
            "assumptions": assumptions or [],
            "warnings": warnings or [],
            "evidence_ids": [item["evidence_id"] for item in evidence],
            "pending_action": pending_action,
            "follow_up_suggestions": [],
            "recommended_images": images[:12],
        }
        return validate_agent_answer(payload, evidence)

    def persist_result(self, state: dict, result: dict):
        if self.store.run_is_cancelled(state["run_id"]):
            return
        assistant_message_id = self.store.add_message(
            user_id=state["user_id"], session_id=state["session_id"], role="assistant",
            content=result["answer"], structured_content=result,
        )
        self.store.maybe_update_session_summary(
            state["user_id"], state["session_id"], assistant_message_id,
            build_session_summary(state, result, assistant_message_id),
        )
        status = "waiting_user" if result.get("pending_action") else "partial" if result.get("partial") else "succeeded"
        self.store.finish_run(
            state["run_id"], status, state.get("tool_call_count", 0),
            model_usage=state.get("model_usage", {}),
            replan_count=state.get("replan_count", 0),
        )

    def enqueue_memory_review(self, state: dict):
        if self.config.long_term_memory_enabled:
            self.store.enqueue_memory_reviews(
                state["user_id"], state["session_id"], state["user_message_id"],
                state["user_input"], self.config.memory_gate_interval_turns,
                answer_facts=state.get("final_answer", {}).get("facts", []),
                relevant_memories=state.get("relevant_memories", []),
            )

    @staticmethod
    def is_confirmation(text):
        return text.strip() in {"确认", "确定", "可以", "保存吧", "执行", "删除吧"}

    @staticmethod
    def is_rejection(text):
        return text.strip() in {"算了", "取消", "不用了", "不要保存", "拒绝"}


def merge_answers(session_id, route, results):
    if len(results) == 1:
        return results[0]
    message = "\n\n".join(item["answer"] for item in results)
    cards = dedupe_entities([card for item in results for card in item.get("cards", [])])
    outfits = [outfit for item in results for outfit in item.get("outfits", [])]
    facts = [fact for item in results for fact in item.get("facts", [])]
    evidence_ids = list(dict.fromkeys(value for item in results for value in item.get("evidence_ids", [])))
    images = list(dict.fromkeys(value for item in results for value in item.get("recommended_images", [])))
    warnings = list(dict.fromkeys(value for item in results for value in item.get("warnings", [])))
    assumptions = list(dict.fromkeys(value for item in results for value in item.get("assumptions", [])))
    suggestions = list(dict.fromkeys(value for item in results for value in item.get("follow_up_suggestions", [])))
    analysis = next((item["analysis"] for item in reversed(results) if item.get("analysis") is not None), None)
    pending_action = next((item["pending_action"] for item in reversed(results) if item.get("pending_action")), None)
    payload = dict(results[-1])
    payload.update({
        "session_id": session_id, "answer": message, "message": message, "route": route,
        "completed_tasks": [item["route"] for item in results], "cards": cards,
        "outfits": outfits, "facts": facts, "evidence_ids": evidence_ids,
        "recommended_images": images, "partial": any(item.get("partial") for item in results),
        "analysis": analysis, "pending_action": pending_action,
        "warnings": warnings, "assumptions": assumptions,
        "follow_up_suggestions": suggestions[:3],
    })
    return AgentAnswer.model_validate(payload).model_dump(mode="json")


def is_clothes_mutation(text):
    clothes_target = any(word in text for word in ("衣服", "衣物", "衣橱")) and "穿搭" not in text
    mutation = any(word in text for word in ("新增", "添加", "修改", "重命名", "删除", "清空"))
    return clothes_target and mutation


def is_outfit_management_request(text):
    return any(word in text for word in ("保存", "存下来", "存为", "重命名", "删除穿搭", "已保存", "我的穿搭", "查看穿搭"))


def with_evidence(data, source):
    return {"ok": True, "data": data, "evidence_id": str(uuid.uuid4()), "source": source, "warnings": [], "error": None}


def normalize_attachments(payload):
    attachments = list(payload.get("attachments") or [])
    if payload.get("image_url") and not attachments:
        attachments = [{"type": "image", "url": payload["image_url"]}]
    return attachments[:1]


def compact_messages(messages):
    return [{"role": item["role"], "content": item["content"][:2_000]} for item in messages[-8:]]


def compact_messages_without_current(messages, current_text):
    history = list(messages)
    if history and history[-1].get("role") == "user" and history[-1].get("content") == current_text:
        history.pop()
    return compact_messages(history)


def model_ready(config):
    return bool(config.deepseek_api_key if config.text_model_provider == "deepseek" else config.ark_api_token)


def unique_ids(values):
    result = []
    for value in values:
        number = int(value)
        if number > 0 and number not in result:
            result.append(number)
    return result


def extract_ordinal(text):
    for token, value in (("第一", 1), ("第1", 1), ("第二", 2), ("第2", 2), ("第三", 3), ("第3", 3), ("第四", 4), ("第4", 4), ("第五", 5), ("第5", 5)):
        if token in text:
            return value
    return None


def extract_save_name(text):
    match = re.search(r"(?:保存|存)(?:第?[一二三123]套)?(?:为|成|叫)?[“\"]?([^”\"，。]+)", text)
    return match.group(1).strip()[:100] if match else ""


def extract_rename(text):
    match = re.search(r"(?:重命名为|改名为|改成)[“\"]?([^”\"，。]+)", text)
    return match.group(1).strip()[:100] if match else ""


def dedupe_entities(items):
    by_id = {}
    for item in items:
        by_id[item.get("id", str(uuid.uuid4()))] = item
    return list(by_id.values())


def simple_fashion_answer(text):
    if "颜色" in text or "配色" in text or "藏蓝" in text:
        return "先确定一个主色，再用白、灰、黑或牛仔蓝做中性过渡；想更醒目时保留一个强调色就够了。"
    return "通常先考虑场合和季节，再统一颜色与风格；涉及你个人衣橱时，我会以数据库中的真实衣物为准。"


def topological_tasks(tasks):
    by_id = {task.task_id: task for task in tasks}
    ordered = []
    visited = set()

    def visit(task):
        if task.task_id in visited:
            return
        for dependency in task.depends_on:
            visit(by_id[dependency])
        visited.add(task.task_id)
        ordered.append(task)

    for task in tasks:
        visit(task)
    return ordered


def empty_usage():
    return {"input_tokens": 0, "output_tokens": 0, "cache_hit_tokens": 0, "cache_miss_tokens": 0}


def usage_from_results(results):
    usage = empty_usage()
    for result in results:
        for key in usage:
            usage[key] += getattr(result, key, None) or 0
    return usage


def add_usage(state, result):
    usage = state.setdefault("model_usage", empty_usage())
    for key in usage:
        usage[key] += getattr(result, key, None) or 0


def build_session_summary(state, result, message_id):
    slots = state.get("active_slots", {})
    constraints = []
    for key in ("occasion", "style", "colors", "garment_roles"):
        value = slots.get(key)
        constraints.extend(value if isinstance(value, list) else [value] if value else [])
    return {
        "user_goal": state["user_input"][:240],
        "confirmed_constraints": list(dict.fromkeys(constraints))[:12],
        "resolved_entities": {"clothes_ids": state.get("referenced_clothes_ids", [])},
        "recommendations_shown": [item.get("candidate_id") for item in result.get("outfits", []) if item.get("candidate_id")],
        "pending_questions": [result["answer"]] if result.get("partial") and not result.get("pending_action") else [],
        "pending_action_id": (result.get("pending_action") or {}).get("action_id"),
        "important_tool_facts": [f"{item['label']}: {item['value']}" for item in result.get("facts", [])],
        "summary_through_message_id": message_id,
    }
