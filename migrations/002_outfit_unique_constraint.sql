-- 001 前置检查确认无重复关系后执行。
ALTER TABLE outfit_clothes
  ADD UNIQUE KEY uk_outfit_clothes_pair (outfit_id, clothes_id);
