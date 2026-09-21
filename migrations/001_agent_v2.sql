-- Agent V2旁路表与安全索引。
-- 执行前请先备份真实数据库，并保存 SHOW CREATE TABLE 输出。

ALTER TABLE users MODIFY password VARCHAR(255) NOT NULL;

ALTER TABLE clothes
  ADD KEY idx_clothes_user_category (user_id, category),
  ADD KEY idx_clothes_user_season (user_id, season),
  ADD KEY idx_clothes_user_updated (user_id, update_time);

ALTER TABLE outfits
  ADD KEY idx_outfits_user_updated (user_id, update_time);

CREATE TABLE IF NOT EXISTS chat_sessions (
  id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  user_id INT NOT NULL,
  title VARCHAR(100) DEFAULT NULL,
  status ENUM('active', 'archived', 'deleted') NOT NULL DEFAULT 'active',
  summary_json JSON DEFAULT NULL,
  summary_through_message_id BIGINT UNSIGNED DEFAULT NULL,
  user_turn_count INT UNSIGNED NOT NULL DEFAULT 0,
  last_memory_gate_turn INT UNSIGNED NOT NULL DEFAULT 0,
  created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  deleted_at DATETIME(3) DEFAULT NULL,
  PRIMARY KEY (id),
  KEY idx_chat_sessions_user_updated (user_id, updated_at),
  CONSTRAINT fk_chat_sessions_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE IF NOT EXISTS chat_messages (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  session_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  user_id INT NOT NULL,
  client_message_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin DEFAULT NULL,
  role ENUM('user', 'assistant') NOT NULL,
  content MEDIUMTEXT NOT NULL,
  structured_content JSON DEFAULT NULL,
  attachments_json JSON DEFAULT NULL,
  referenced_clothes_json JSON DEFAULT NULL,
  referenced_outfits_json JSON DEFAULT NULL,
  model_provider VARCHAR(32) DEFAULT NULL,
  model_name VARCHAR(100) DEFAULT NULL,
  input_tokens INT UNSIGNED DEFAULT NULL,
  output_tokens INT UNSIGNED DEFAULT NULL,
  created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  PRIMARY KEY (id),
  UNIQUE KEY uk_chat_message_idempotency (session_id, client_message_id),
  KEY idx_chat_messages_session_id (session_id, id),
  KEY idx_chat_messages_user_created (user_id, created_at),
  CONSTRAINT fk_chat_messages_session FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE,
  CONSTRAINT fk_chat_messages_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE IF NOT EXISTS user_memories (
  id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  user_id INT NOT NULL,
  memory_type ENUM('preference', 'avoidance', 'wardrobe_fact', 'correction', 'habit', 'episodic') NOT NULL,
  memory_key VARCHAR(191) NOT NULL,
  content TEXT NOT NULL,
  structured_value JSON DEFAULT NULL,
  confidence DECIMAL(4,3) NOT NULL,
  status ENUM('active', 'superseded', 'deleted', 'expired') NOT NULL DEFAULT 'active',
  source_session_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin DEFAULT NULL,
  source_message_id BIGINT UNSIGNED DEFAULT NULL,
  supersedes_memory_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin DEFAULT NULL,
  evidence_count SMALLINT UNSIGNED NOT NULL DEFAULT 1,
  valid_from DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  valid_until DATETIME(3) DEFAULT NULL,
  last_confirmed_at DATETIME(3) DEFAULT NULL,
  created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (id),
  KEY idx_user_memories_lookup (user_id, status, memory_type),
  KEY idx_user_memories_key (user_id, memory_key, status),
  KEY idx_user_memories_source (source_message_id),
  CONSTRAINT fk_user_memories_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_user_memories_session FOREIGN KEY (source_session_id) REFERENCES chat_sessions(id) ON DELETE SET NULL,
  CONSTRAINT fk_user_memories_message FOREIGN KEY (source_message_id) REFERENCES chat_messages(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE IF NOT EXISTS memory_review_jobs (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id INT NOT NULL,
  session_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  trigger_message_id BIGINT UNSIGNED DEFAULT NULL,
  review_type ENUM('per_turn', 'gate') NOT NULL,
  turn_from INT UNSIGNED NOT NULL,
  turn_to INT UNSIGNED NOT NULL,
  idempotency_key CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  status ENUM('pending', 'running', 'succeeded', 'failed', 'dead') NOT NULL DEFAULT 'pending',
  attempts TINYINT UNSIGNED NOT NULL DEFAULT 0,
  input_json JSON DEFAULT NULL,
  result_json JSON DEFAULT NULL,
  error_code VARCHAR(64) DEFAULT NULL,
  next_attempt_at DATETIME(3) DEFAULT NULL,
  created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (id),
  UNIQUE KEY uk_memory_review_idempotency (idempotency_key),
  KEY idx_memory_review_worker (status, next_attempt_at, id),
  KEY idx_memory_review_session (session_id, turn_to),
  CONSTRAINT fk_memory_review_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_memory_review_session FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE,
  CONSTRAINT fk_memory_review_message FOREIGN KEY (trigger_message_id) REFERENCES chat_messages(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE IF NOT EXISTS memory_gate_checkpoints (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id INT NOT NULL,
  session_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  turn_from INT UNSIGNED NOT NULL,
  turn_to INT UNSIGNED NOT NULL,
  review_job_id BIGINT UNSIGNED DEFAULT NULL,
  completed_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  PRIMARY KEY (id),
  UNIQUE KEY uk_memory_gate_range (session_id, turn_from, turn_to),
  KEY idx_memory_gate_user (user_id, completed_at),
  CONSTRAINT fk_memory_gate_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_memory_gate_session FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE,
  CONSTRAINT fk_memory_gate_job FOREIGN KEY (review_job_id) REFERENCES memory_review_jobs(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE IF NOT EXISTS pending_outfit_actions (
  id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  user_id INT NOT NULL,
  session_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  operation ENUM('create', 'update', 'delete') NOT NULL,
  target_outfit_id INT DEFAULT NULL,
  payload_json JSON NOT NULL,
  payload_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  human_summary TEXT NOT NULL,
  status ENUM('pending', 'approved', 'executing', 'executed', 'rejected', 'expired', 'failed') NOT NULL DEFAULT 'pending',
  expires_at DATETIME(3) NOT NULL,
  approved_at DATETIME(3) DEFAULT NULL,
  executed_at DATETIME(3) DEFAULT NULL,
  result_json JSON DEFAULT NULL,
  created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (id),
  KEY idx_pending_action_user_status (user_id, status, expires_at),
  KEY idx_pending_action_session (session_id, created_at),
  CONSTRAINT fk_pending_action_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_pending_action_session FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE,
  CONSTRAINT fk_pending_action_outfit FOREIGN KEY (target_outfit_id) REFERENCES outfits(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE IF NOT EXISTS agent_runs (
  id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  user_id INT NOT NULL,
  session_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  trigger_message_id BIGINT UNSIGNED DEFAULT NULL,
  primary_route VARCHAR(40) DEFAULT NULL,
  status ENUM('running', 'waiting_user', 'succeeded', 'partial', 'failed', 'cancelled') NOT NULL DEFAULT 'running',
  model_provider VARCHAR(32) DEFAULT NULL,
  model_name VARCHAR(100) DEFAULT NULL,
  prompt_version VARCHAR(40) DEFAULT NULL,
  graph_version VARCHAR(40) DEFAULT NULL,
  replan_count TINYINT UNSIGNED NOT NULL DEFAULT 0,
  tool_call_count TINYINT UNSIGNED NOT NULL DEFAULT 0,
  input_tokens INT UNSIGNED DEFAULT NULL,
  output_tokens INT UNSIGNED DEFAULT NULL,
  reasoning_tokens INT UNSIGNED DEFAULT NULL,
  cache_hit_tokens INT UNSIGNED DEFAULT NULL,
  cache_miss_tokens INT UNSIGNED DEFAULT NULL,
  estimated_cost_cny DECIMAL(12,6) DEFAULT NULL,
  latency_ms INT UNSIGNED DEFAULT NULL,
  error_code VARCHAR(64) DEFAULT NULL,
  created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  completed_at DATETIME(3) DEFAULT NULL,
  PRIMARY KEY (id),
  KEY idx_agent_runs_session (session_id, created_at),
  KEY idx_agent_runs_user_status (user_id, status, created_at),
  CONSTRAINT fk_agent_runs_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_agent_runs_session FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE,
  CONSTRAINT fk_agent_runs_message FOREIGN KEY (trigger_message_id) REFERENCES chat_messages(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE IF NOT EXISTS clothes_embeddings (
  clothes_id INT NOT NULL,
  user_id INT NOT NULL,
  embedding_model VARCHAR(100) NOT NULL,
  dimensions SMALLINT UNSIGNED NOT NULL,
  content_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  embedding MEDIUMBLOB NOT NULL,
  created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (clothes_id, embedding_model),
  KEY idx_clothes_embeddings_user_model (user_id, embedding_model),
  CONSTRAINT fk_clothes_embeddings_clothes FOREIGN KEY (clothes_id) REFERENCES clothes(id) ON DELETE CASCADE,
  CONSTRAINT fk_clothes_embeddings_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE IF NOT EXISTS agent_tool_calls (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  run_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  user_id INT NOT NULL,
  tool_name VARCHAR(64) NOT NULL,
  call_fingerprint CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  status ENUM('running', 'succeeded', 'failed', 'skipped') NOT NULL,
  safe_args_json JSON DEFAULT NULL,
  evidence_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin DEFAULT NULL,
  row_count INT UNSIGNED DEFAULT NULL,
  latency_ms INT UNSIGNED DEFAULT NULL,
  error_code VARCHAR(64) DEFAULT NULL,
  created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  completed_at DATETIME(3) DEFAULT NULL,
  PRIMARY KEY (id),
  KEY idx_agent_tool_calls_run (run_id, id),
  KEY idx_agent_tool_calls_fingerprint (run_id, call_fingerprint),
  CONSTRAINT fk_agent_tool_calls_run FOREIGN KEY (run_id) REFERENCES agent_runs(id) ON DELETE CASCADE,
  CONSTRAINT fk_agent_tool_calls_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
