import hashlib
import json
import uuid
from datetime import datetime, timedelta


class AgentSchemaMissing(RuntimeError):
    pass


class ActionConflict(ValueError):
    pass


class AgentStore:
    def __init__(self, connect):
        self.connect = connect

    def create_session(self, user_id: int, title: str | None = None):
        session_id = str(uuid.uuid4())
        with self.connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO chat_sessions (id, user_id, title)
                    VALUES (%s, %s, %s)
                    """,
                    (session_id, user_id, title),
                )
            conn.commit()
        return {"session_id": session_id, "created_at": datetime.now().isoformat()}

    def ensure_session(self, user_id: int, session_id: str | None):
        if not session_id or not is_uuid(session_id):
            return self.create_session(user_id)["session_id"]
        with self.connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id
                    FROM chat_sessions
                    WHERE id = %s AND user_id = %s AND status = 'active'
                    """,
                    (session_id, user_id),
                )
                if cursor.fetchone():
                    return session_id
        raise KeyError("会话不存在")

    def get_message_by_client_id(self, user_id: int, session_id: str, client_message_id: str | None):
        if not client_message_id:
            return None
        with self.connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id FROM chat_messages
                    WHERE user_id = %s AND session_id = %s AND client_message_id = %s AND role = 'user'
                    """,
                    (user_id, session_id, client_message_id),
                )
                user_message = cursor.fetchone()
                if not user_message:
                    return None
                cursor.execute(
                    """
                    SELECT structured_content
                    FROM chat_messages
                    WHERE user_id = %s AND session_id = %s AND role = 'assistant' AND id > %s
                    ORDER BY id ASC LIMIT 1
                    """,
                    (user_id, session_id, user_message["id"]),
                )
                answer = cursor.fetchone()
        return load_json(answer["structured_content"]) if answer and answer.get("structured_content") else None

    def add_message(
        self,
        *,
        user_id: int,
        session_id: str,
        role: str,
        content: str,
        client_message_id: str | None = None,
        structured_content: dict | None = None,
        attachments: list | None = None,
    ):
        structured_json = dump_json(structured_content) if structured_content is not None else None
        attachments_json = dump_json(attachments) if attachments is not None else None
        with self.connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO chat_messages (
                      session_id, user_id, client_message_id, role, content,
                      structured_content, attachments_json
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE id = LAST_INSERT_ID(id)
                    """,
                    (
                        session_id,
                        user_id,
                        client_message_id,
                        role,
                        content,
                        structured_json,
                        attachments_json,
                    ),
                )
                message_id = cursor.lastrowid
                inserted = cursor.rowcount == 1
                if role == "user" and inserted:
                    cursor.execute(
                        """
                        UPDATE chat_sessions
                        SET user_turn_count = user_turn_count + 1
                        WHERE id = %s AND user_id = %s
                        """,
                        (session_id, user_id),
                    )
            conn.commit()
        return message_id

    def list_messages(self, user_id: int, session_id: str, limit=50):
        with self.connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, role, content, structured_content, created_at
                    FROM chat_messages
                    WHERE user_id = %s AND session_id = %s
                    ORDER BY id DESC
                    LIMIT %s
                    """,
                    (user_id, session_id, min(int(limit), 100)),
                )
                rows = list(cursor.fetchall())
        for row in rows:
            row["structured_content"] = load_json(row.get("structured_content"))
        return list(reversed(rows))

    def session_context(self, user_id: int, session_id: str):
        with self.connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT summary_json, user_turn_count, last_memory_gate_turn
                    FROM chat_sessions
                    WHERE id = %s AND user_id = %s AND status = 'active'
                    """,
                    (session_id, user_id),
                )
                row = cursor.fetchone()
        if not row:
            raise KeyError("会话不存在")
        row["summary"] = load_json(row.pop("summary_json")) or {}
        return row

    def create_run(self, user_id: int, session_id: str, trigger_message_id: int | None, route: str | None):
        run_id = str(uuid.uuid4())
        with self.connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE agent_runs SET status='cancelled', completed_at=CURRENT_TIMESTAMP(3) "
                    "WHERE user_id=%s AND session_id=%s AND status='running'",
                    (user_id, session_id),
                )
                cursor.execute(
                    """
                    INSERT INTO agent_runs (id, user_id, session_id, trigger_message_id, primary_route, graph_version)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (run_id, user_id, session_id, trigger_message_id, route, "agent-v2-1.0"),
                )
            conn.commit()
        return run_id

    def cancel_active_run(self, user_id: int, session_id: str):
        with self.connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE agent_runs SET status='cancelled', completed_at=CURRENT_TIMESTAMP(3) "
                    "WHERE user_id=%s AND session_id=%s AND status='running'",
                    (user_id, session_id),
                )
                changed = cursor.rowcount
            conn.commit()
        return changed

    def run_is_cancelled(self, run_id: str):
        with self.connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT status FROM agent_runs WHERE id=%s", (run_id,))
                row = cursor.fetchone()
        return bool(row and row["status"] == "cancelled")

    def update_run_route(self, run_id: str, route: str, provider: str, model: str):
        with self.connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE agent_runs
                    SET primary_route=%s, model_provider=%s, model_name=%s, prompt_version=%s
                    WHERE id=%s
                    """,
                    (route, provider, model, "router-1.0", run_id),
                )
            conn.commit()

    def record_tool_calls(self, run_id: str, user_id: int, steps: list[dict], result: dict):
        evidence_ids = result.get("evidence_ids", [])
        row_count = len(result.get("cards", [])) + len(result.get("outfits", []))
        with self.connect() as conn:
            with conn.cursor() as cursor:
                for index, step in enumerate(steps):
                    safe_args = step.get("args", {})
                    fingerprint = hashlib.sha256(
                        f"{step['action']}:{dump_json(safe_args)}".encode()
                    ).hexdigest()
                    cursor.execute(
                        "SELECT 1 FROM agent_tool_calls WHERE run_id=%s AND call_fingerprint=%s LIMIT 1",
                        (run_id, fingerprint),
                    )
                    if cursor.fetchone():
                        continue
                    cursor.execute(
                        """
                        INSERT INTO agent_tool_calls (
                          run_id, user_id, tool_name, call_fingerprint, status,
                          safe_args_json, evidence_id, row_count, completed_at
                        ) VALUES (%s, %s, %s, %s, 'succeeded', %s, %s, %s, CURRENT_TIMESTAMP(3))
                        """,
                        (
                            run_id, user_id, step["action"], fingerprint,
                            dump_json(safe_args),
                            evidence_ids[index] if index < len(evidence_ids) else None,
                            row_count,
                        ),
                    )
            conn.commit()

    def record_tool_call(
        self, run_id: str, user_id: int, tool_name: str, safe_args: dict,
        evidence_id: str | None = None, row_count: int | None = None,
    ):
        fingerprint = hashlib.sha256(f"{tool_name}:{dump_json(safe_args)}".encode()).hexdigest()
        with self.connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO agent_tool_calls (
                      run_id, user_id, tool_name, call_fingerprint, status,
                      safe_args_json, evidence_id, row_count, completed_at
                    ) VALUES (%s, %s, %s, %s, 'succeeded', %s, %s, %s, CURRENT_TIMESTAMP(3))
                    """,
                    (run_id, user_id, tool_name, fingerprint, dump_json(safe_args), evidence_id, row_count),
                )
            conn.commit()

    def finish_run(
        self, run_id: str, status: str, tool_call_count=0,
        error_code: str | None = None, model_usage: dict | None = None,
        replan_count: int = 0,
    ):
        usage = model_usage or {}
        with self.connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE agent_runs
                    SET status = %s, tool_call_count = %s, error_code = %s,
                        input_tokens = %s, output_tokens = %s,
                        cache_hit_tokens = %s, cache_miss_tokens = %s,
                        replan_count = %s,
                        latency_ms = TIMESTAMPDIFF(MICROSECOND, created_at, CURRENT_TIMESTAMP(3)) DIV 1000,
                        completed_at = CURRENT_TIMESTAMP(3)
                    WHERE id = %s AND status <> 'cancelled'
                    """,
                    (
                        status, tool_call_count, error_code,
                        usage.get("input_tokens") or None,
                        usage.get("output_tokens") or None,
                        usage.get("cache_hit_tokens") or None,
                        usage.get("cache_miss_tokens") or None,
                        replan_count,
                        run_id,
                    ),
                )
            conn.commit()

    def create_pending_action(self, *, user_id: int, session_id: str, payload: dict, human_summary: str):
        action_id = str(uuid.uuid4())
        payload_json = dump_json(payload)
        payload_hash = hashlib.sha256(payload_json.encode()).hexdigest()
        expires_at = datetime.now() + timedelta(minutes=10)
        with self.connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO pending_outfit_actions (
                      id, user_id, session_id, operation, target_outfit_id,
                      payload_json, payload_hash, human_summary, expires_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        action_id,
                        user_id,
                        session_id,
                        payload.get("operation", "create"),
                        payload.get("target_outfit_id"),
                        payload_json,
                        payload_hash,
                        human_summary,
                        expires_at,
                    ),
                )
            conn.commit()
        return {
            "action_id": action_id,
            "kind": payload.get("kind", "create_outfit"),
            "name": payload.get("name", ""),
            "clothes_ids": payload.get("clothes_ids", []),
            "summary": human_summary,
            "expires_at": expires_at.timestamp(),
            "payload_hash": payload_hash,
        }

    def latest_pending_action(self, user_id: int, session_id: str):
        with self.connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT *
                    FROM pending_outfit_actions
                    WHERE user_id = %s AND session_id = %s AND status = 'pending' AND expires_at > CURRENT_TIMESTAMP(3)
                    ORDER BY created_at DESC
                    LIMIT 2
                    """,
                    (user_id, session_id),
                )
                rows = cursor.fetchall()
        if len(rows) != 1:
            return None
        row = rows[0]
        row["payload"] = json.loads(row.pop("payload_json"))
        return row

    def approve_pending_action(self, user_id: int, session_id: str, action_id: str, expected_hash: str | None = None):
        action = self.get_pending_action(user_id, session_id, action_id)
        if not action:
            return None
        if expected_hash and action["payload_hash"] != expected_hash:
            raise ValueError("确认摘要已变化，请重新确认")

        with self.connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE pending_outfit_actions
                    SET status = 'approved', approved_at = CURRENT_TIMESTAMP(3)
                    WHERE id = %s AND user_id = %s AND session_id = %s
                      AND status = 'pending' AND expires_at > CURRENT_TIMESTAMP(3)
                    """,
                    (action_id, user_id, session_id),
                )
                if cursor.rowcount != 1:
                    conn.rollback()
                    return None
            conn.commit()
        action["status"] = "approved"
        return action

    def mark_action_executed(self, user_id: int, action_id: str, result: dict):
        with self.connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE pending_outfit_actions
                    SET status = 'executed', executed_at = CURRENT_TIMESTAMP(3), result_json = %s
                    WHERE id = %s AND user_id = %s
                    """,
                    (dump_json(result), action_id, user_id),
                )
            conn.commit()

    def execute_outfit_action(
        self, user_id: int, session_id: str, action_id: str, expected_hash: str,
        client_decision_id: str | None = None,
    ):
        with self.connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT *
                    FROM pending_outfit_actions
                    WHERE id = %s AND user_id = %s AND session_id = %s
                    FOR UPDATE
                    """,
                    (action_id, user_id, session_id),
                )
                action = cursor.fetchone()
                if not action:
                    raise ValueError("待确认操作不存在")
                if action["status"] == "executed":
                    return json.loads(action["result_json"])
                if action["payload_hash"] != expected_hash:
                    raise ActionConflict("确认摘要已变化，请重新确认")
                if action["status"] != "pending" or action["expires_at"] <= datetime.now():
                    raise ActionConflict("待确认操作已处理或已过期")

                payload = json.loads(action["payload_json"])
                cursor.execute(
                    """
                    UPDATE pending_outfit_actions
                    SET status = 'executing', approved_at = CURRENT_TIMESTAMP(3),
                        client_decision_id = COALESCE(client_decision_id, %s)
                    WHERE id = %s AND user_id = %s AND status = 'pending'
                    """,
                    (client_decision_id, action_id, user_id),
                )

                result = self.apply_outfit_change(cursor, user_id, payload)
                cursor.execute(
                    """
                    UPDATE pending_outfit_actions
                    SET status = 'executed', executed_at = CURRENT_TIMESTAMP(3), result_json = %s
                    WHERE id = %s AND user_id = %s
                    """,
                    (dump_json(result), action_id, user_id),
                )
            conn.commit()
        return result

    def apply_outfit_change(self, cursor, user_id: int, payload: dict):
        operation = payload.get("operation")
        if operation == "create":
            clothes = self.lock_action_clothes(cursor, user_id, payload["clothes_ids"])
            image_url = next((item["image_url"] for item in clothes if item.get("image_url")), "")
            cursor.execute(
                "INSERT INTO outfits (name, description, image_url, user_id) VALUES (%s, %s, %s, %s)",
                (payload["name"], payload.get("description", ""), image_url, user_id),
            )
            outfit_id = cursor.lastrowid
            self.replace_outfit_clothes(cursor, outfit_id, clothes)
            return self.outfit_result(outfit_id, payload["name"], payload.get("description", ""), image_url, clothes)

        outfit_id = int(payload.get("target_outfit_id") or 0)
        cursor.execute(
            "SELECT id, name, description, image_url, update_time FROM outfits "
            "WHERE id=%s AND user_id=%s FOR UPDATE",
            (outfit_id, user_id),
        )
        existing = cursor.fetchone()
        if not existing:
            raise ValueError("穿搭不存在")
        expected = payload.get("expected_updated_at")
        if expected and str(existing["update_time"]) != expected:
            raise ActionConflict("穿搭在确认前已发生变化，请基于最新内容重新确认")

        if operation == "delete":
            cursor.execute("DELETE FROM outfits WHERE id=%s AND user_id=%s", (outfit_id, user_id))
            return {"id": outfit_id, "name": existing["name"], "deleted": True, "clothes": []}
        if operation != "update":
            raise ValueError("不支持的穿搭操作")

        clothes = self.lock_action_clothes(cursor, user_id, payload["clothes_ids"])
        name = payload.get("name", existing["name"])
        description = payload.get("description", existing["description"] or "")
        image_url = payload.get("image_url") or next(
            (item["image_url"] for item in clothes if item.get("image_url")), existing["image_url"] or ""
        )
        cursor.execute(
            "UPDATE outfits SET name=%s, description=%s, image_url=%s WHERE id=%s AND user_id=%s",
            (name, description, image_url, outfit_id, user_id),
        )
        cursor.execute("DELETE FROM outfit_clothes WHERE outfit_id=%s", (outfit_id,))
        self.replace_outfit_clothes(cursor, outfit_id, clothes)
        return self.outfit_result(outfit_id, name, description, image_url, clothes)

    @staticmethod
    def replace_outfit_clothes(cursor, outfit_id: int, clothes: list[dict]):
        for item in clothes:
            cursor.execute(
                "INSERT INTO outfit_clothes (outfit_id, clothes_id, position) VALUES (%s, %s, %s)",
                (outfit_id, item["id"], item["category"]),
            )

    @staticmethod
    def outfit_result(outfit_id, name, description, image_url, clothes):
        return {
            "id": outfit_id,
            "name": name,
            "description": description,
            "image_url": image_url,
            "clothes": clothes,
        }

    def lock_action_clothes(self, cursor, user_id: int, clothes_ids: list[int]):
        ids = unique_ints(clothes_ids)
        if not 1 <= len(ids) <= 4:
            raise ValueError("穿搭必须包含 1 到 4 件衣物")
        placeholders = ", ".join(["%s"] * len(ids))
        cursor.execute(
            f"""
            SELECT id, name, image_url, category, sub_category, brand, style,
                   color, sub_color, season, material, occasion, description, thickness
            FROM clothes
            WHERE user_id = %s AND id IN ({placeholders})
            FOR UPDATE
            """,
            [user_id, *ids],
        )
        rows = cursor.fetchall()
        if len(rows) != len(ids):
            raise ValueError("穿搭中包含不存在或不属于当前用户的衣物")
        by_id = {row["id"]: normalize_action_clothes(row) for row in rows}
        clothes = [by_id[item_id] for item_id in ids]
        validate_outfit_structure(clothes)
        return clothes

    def reject_pending_action(self, user_id: int, session_id: str, action_id: str, client_decision_id: str | None = None):
        with self.connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE pending_outfit_actions
                    SET status = 'rejected', client_decision_id = COALESCE(client_decision_id, %s)
                    WHERE id = %s AND user_id = %s AND session_id = %s AND status = 'pending'
                    """,
                    (client_decision_id, action_id, user_id, session_id),
                )
            conn.commit()

    def list_memories(self, user_id: int, text: str | None = None, limit: int | None = None):
        with self.connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, memory_type, memory_key, content, confidence, created_at, updated_at
                    FROM user_memories
                    WHERE user_id = %s AND status = 'active'
                    ORDER BY memory_type, updated_at DESC
                    """,
                    (user_id,),
                )
                rows = list(cursor.fetchall())
        if text:
            rows.sort(key=lambda item: memory_relevance(item, text), reverse=True)
        return rows[:limit] if limit else rows

    def enqueue_memory_reviews(
        self, user_id: int, session_id: str, message_id: int, text: str, interval: int,
        answer_facts: list | None = None, relevant_memories: list | None = None,
    ):
        context = self.session_context(user_id, session_id)
        turn = int(context["user_turn_count"])
        jobs = [("per_turn", turn, turn)]
        last_gate = int(context["last_memory_gate_turn"])
        if turn - last_gate >= interval:
            jobs.append(("gate", last_gate + 1, turn))

        with self.connect() as conn:
            with conn.cursor() as cursor:
                for review_type, turn_from, turn_to in jobs:
                    key = hashlib.sha256(
                        f"{user_id}:{session_id}:{review_type}:{turn_from}:{turn_to}".encode()
                    ).hexdigest()
                    cursor.execute(
                        """
                        INSERT IGNORE INTO memory_review_jobs (
                          user_id, session_id, trigger_message_id, review_type,
                          turn_from, turn_to, idempotency_key, input_json
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            user_id, session_id, message_id, review_type, turn_from, turn_to, key,
                            dump_json({
                                "user_text": text,
                                "answer_facts": answer_facts or [],
                                "relevant_memories": relevant_memories or [],
                            }),
                        ),
                    )
            conn.commit()

    def claim_memory_review_job(self):
        with self.connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT * FROM memory_review_jobs
                    WHERE (
                        status IN ('pending', 'failed')
                        OR (status = 'running' AND updated_at < DATE_SUB(CURRENT_TIMESTAMP(3), INTERVAL 2 MINUTE))
                    )
                      AND attempts < 3
                      AND (next_attempt_at IS NULL OR next_attempt_at <= CURRENT_TIMESTAMP(3))
                    ORDER BY id LIMIT 1 FOR UPDATE SKIP LOCKED
                    """
                )
                job = cursor.fetchone()
                if not job:
                    conn.commit()
                    return None
                cursor.execute(
                    "UPDATE memory_review_jobs SET status='running', attempts=attempts+1 WHERE id=%s",
                    (job["id"],),
                )
            conn.commit()
        job["input"] = load_json(job.pop("input_json")) or {}
        return job

    def finish_memory_review_job(self, job: dict, operations: list[dict]):
        with self.connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT status FROM memory_review_jobs WHERE id=%s FOR UPDATE", (job["id"],))
                current = cursor.fetchone()
                if not current or current["status"] == "succeeded":
                    conn.commit()
                    return
                for operation in operations:
                    if operation.get("op", "upsert") == "delete":
                        cursor.execute(
                            "UPDATE user_memories SET status='deleted' "
                            "WHERE user_id=%s AND memory_key=%s AND status='active'",
                            (job["user_id"], operation["memory_key"]),
                        )
                        continue
                    if operation.get("op", "upsert") != "upsert":
                        continue
                    cursor.execute(
                        "UPDATE user_memories SET status='superseded' "
                        "WHERE user_id=%s AND memory_key=%s AND status='active'",
                        (job["user_id"], operation["memory_key"]),
                    )
                    cursor.execute(
                        """
                        INSERT INTO user_memories (
                          id, user_id, memory_type, memory_key, content, structured_value,
                          confidence, source_session_id, source_message_id, last_confirmed_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP(3))
                        """,
                        (
                            str(uuid.uuid4()), job["user_id"], operation["memory_type"],
                            operation["memory_key"], operation["content"],
                            dump_json(operation.get("structured_value") or {}), operation["confidence"],
                            job["session_id"], job.get("trigger_message_id"),
                        ),
                    )
                cursor.execute(
                    "UPDATE memory_review_jobs SET status='succeeded', result_json=%s, error_code=NULL WHERE id=%s",
                    (dump_json({"operations": operations}), job["id"]),
                )
                if job["review_type"] == "gate":
                    cursor.execute(
                        """
                        INSERT IGNORE INTO memory_gate_checkpoints
                          (user_id, session_id, turn_from, turn_to, review_job_id)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (job["user_id"], job["session_id"], job["turn_from"], job["turn_to"], job["id"]),
                    )
                    cursor.execute(
                        "UPDATE chat_sessions SET last_memory_gate_turn=%s WHERE id=%s AND user_id=%s",
                        (job["turn_to"], job["session_id"], job["user_id"]),
                    )
            conn.commit()

    def memory_gate_context(self, user_id: int, session_id: str, turn_count: int):
        messages = self.list_messages(user_id, session_id, min(turn_count * 2 + 4, 50))
        return {
            "user_messages": [item["content"] for item in messages if item["role"] == "user"],
            "active_memories": self.list_memories(user_id),
        }

    def maybe_update_session_summary(self, user_id: int, session_id: str, message_id: int, summary: dict):
        with self.connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT COUNT(*) AS total FROM chat_messages WHERE session_id=%s AND user_id=%s",
                    (session_id, user_id),
                )
                if cursor.fetchone()["total"] % 6:
                    return False
                cursor.execute(
                    "UPDATE chat_sessions SET summary_json=%s, summary_through_message_id=%s "
                    "WHERE id=%s AND user_id=%s",
                    (dump_json(summary), message_id, session_id, user_id),
                )
            conn.commit()
        return True

    def fail_memory_review_job(self, job_id: int, attempts: int, error_code: str):
        status = "dead" if attempts >= 3 else "failed"
        with self.connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE memory_review_jobs SET status=%s, error_code=%s, "
                    "next_attempt_at=DATE_ADD(CURRENT_TIMESTAMP(3), INTERVAL 30 SECOND) WHERE id=%s",
                    (status, error_code[:64], job_id),
                )
            conn.commit()

    def delete_session(self, user_id: int, session_id: str):
        with self.connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM chat_sessions WHERE id=%s AND user_id=%s",
                    (session_id, user_id),
                )
                changed = cursor.rowcount == 1
            conn.commit()
        return changed

    def delete_all_memories(self, user_id: int):
        with self.connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE user_memories SET status='deleted' WHERE user_id=%s AND status='active'",
                    (user_id,),
                )
                changed = cursor.rowcount
            conn.commit()
        return changed

    def upsert_memory(
        self,
        *,
        user_id: int,
        memory_type: str,
        memory_key: str,
        content: str,
        confidence: float,
        source_session_id: str,
        source_message_id: int | None,
        structured_value: dict | None = None,
    ):
        memory_id = str(uuid.uuid4())
        with self.connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE user_memories
                    SET status = 'superseded'
                    WHERE user_id = %s AND memory_key = %s AND status = 'active'
                    """,
                    (user_id, memory_key),
                )
                cursor.execute(
                    """
                    INSERT INTO user_memories (
                      id, user_id, memory_type, memory_key, content, structured_value,
                      confidence, source_session_id, source_message_id, last_confirmed_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP(3))
                    """,
                    (
                        memory_id,
                        user_id,
                        memory_type,
                        memory_key,
                        content,
                        dump_json(structured_value) if structured_value else None,
                        confidence,
                        source_session_id,
                        source_message_id,
                    ),
                )
            conn.commit()
        return memory_id

    def delete_memory(self, user_id: int, memory_id: str):
        with self.connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE user_memories
                    SET status = 'deleted'
                    WHERE id = %s AND user_id = %s AND status = 'active'
                    """,
                    (memory_id, user_id),
                )
                changed = cursor.rowcount == 1
            conn.commit()
        return changed

    def update_memory(self, user_id: int, memory_id: str, content: str):
        with self.connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE user_memories SET content=%s, last_confirmed_at=CURRENT_TIMESTAMP(3) "
                    "WHERE id=%s AND user_id=%s AND status='active'",
                    (content, memory_id, user_id),
                )
                changed = cursor.rowcount == 1
            conn.commit()
        return changed

    def get_pending_action(self, user_id: int, session_id: str, action_id: str):
        with self.connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT *
                    FROM pending_outfit_actions
                    WHERE id = %s AND user_id = %s AND session_id = %s
                    """,
                    (action_id, user_id, session_id),
                )
                row = cursor.fetchone()
        if not row:
            return None
        row["payload"] = json.loads(row.pop("payload_json"))
        return row

    def get_pending_action_for_user(self, user_id: int, action_id: str):
        with self.connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM pending_outfit_actions WHERE id = %s AND user_id = %s",
                    (action_id, user_id),
                )
                row = cursor.fetchone()
        if not row:
            return None
        row["payload"] = json.loads(row.pop("payload_json"))
        return row


def dump_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def load_json(value):
    if value is None or isinstance(value, (dict, list)):
        return value
    return json.loads(value)


def is_uuid(value):
    try:
        uuid.UUID(str(value))
        return True
    except ValueError:
        return False


def unique_ints(values):
    result = []
    for value in values:
        number = int(value)
        if number not in result:
            result.append(number)
    return result


def normalize_action_clothes(row):
    from agent_service.query.semantic import garment_role

    item = dict(row)
    occasion = item.get("occasion") or ""
    item["occasions"] = [part.strip() for part in occasion.replace("，", ",").split(",") if part.strip()]
    item["subCategory"] = item.get("sub_category") or ""
    item["subColor"] = item.get("sub_color") or ""
    item["garment_role"] = garment_role(item)
    return item


def validate_outfit_structure(clothes):
    roles = [item["garment_role"] for item in clothes]
    if any(roles.count(role) > 1 for role in ("top", "bottom", "suit", "outerwear")):
        raise ValueError("每个穿搭角色最多一件")
    role_set = set(roles)
    legal = role_set in (
        {"top", "bottom"},
        {"top", "bottom", "outerwear"},
        {"suit"},
        {"suit", "outerwear"},
    )
    if not legal:
        raise ValueError("穿搭结构必须是上装+下装、上装+下装+外套、套装或套装+外套")


def memory_relevance(memory, text):
    normalized = "".join(character.lower() for character in text if character.isalnum())
    content = "".join(
        character.lower()
        for character in f"{memory.get('memory_key', '')}{memory.get('content', '')}"
        if character.isalnum()
    )
    text_pairs = {normalized[index:index + 2] for index in range(max(len(normalized) - 1, 0))}
    content_pairs = {content[index:index + 2] for index in range(max(len(content) - 1, 0))}
    overlap = len(text_pairs & content_pairs) / max(len(text_pairs | content_pairs), 1)
    exact = 1.0 if normalized and normalized in content else 0.0
    type_match = 1.0 if memory.get("memory_type") in {"avoidance", "correction"} else 0.6
    confidence = float(memory.get("confidence") or 0)
    age_days = max((datetime.now() - memory["updated_at"]).days, 0)
    recency = 2 ** (-age_days / 180)
    return 0.45 * max(exact, overlap) + 0.25 * type_match + 0.20 * confidence + 0.10 * recency
