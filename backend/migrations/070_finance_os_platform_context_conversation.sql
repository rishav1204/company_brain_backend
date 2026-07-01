-- Module 38: conversation state for Platform Context Engine working memory

ALTER TABLE finance_os.goals
  ADD COLUMN IF NOT EXISTS conversation_state jsonb NOT NULL DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS idx_fin_os_goals_conversation
  ON finance_os.goals (org_id, updated_at DESC)
  WHERE conversation_state != '{}'::jsonb;
