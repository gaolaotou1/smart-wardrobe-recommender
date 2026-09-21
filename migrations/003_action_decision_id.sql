ALTER TABLE pending_outfit_actions
  ADD COLUMN client_decision_id VARCHAR(64) DEFAULT NULL AFTER result_json,
  ADD UNIQUE KEY uk_pending_action_user_decision (user_id, client_decision_id);
