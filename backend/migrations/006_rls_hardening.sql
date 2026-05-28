-- Harden tenant isolation: shared org resolver, FORCE RLS on eval tables,
-- and WITH CHECK on all tenant-scoped policies to block cross-tenant writes.

CREATE OR REPLACE FUNCTION app_current_org_id()
RETURNS UUID AS $$
    SELECT NULLIF(current_setting('app.current_org', true), '')::UUID
$$ LANGUAGE sql STABLE;

ALTER TABLE qa_gold_examples FORCE ROW LEVEL SECURITY;
ALTER TABLE retrieval_judgments FORCE ROW LEVEL SECURITY;
ALTER TABLE safety_events FORCE ROW LEVEL SECURITY;
ALTER TABLE feedback_events FORCE ROW LEVEL SECURITY;
ALTER TABLE eval_runs FORCE ROW LEVEL SECURITY;

ALTER POLICY users_org_isolation ON users
    USING (org_id = app_current_org_id())
    WITH CHECK (org_id = app_current_org_id());

ALTER POLICY user_roles_org_isolation ON user_roles
    USING (org_id = app_current_org_id())
    WITH CHECK (org_id = app_current_org_id());

ALTER POLICY sources_org_isolation ON data_sources
    USING (org_id = app_current_org_id())
    WITH CHECK (org_id = app_current_org_id());

ALTER POLICY ingestion_runs_org_isolation ON ingestion_runs
    USING (org_id = app_current_org_id())
    WITH CHECK (org_id = app_current_org_id());

ALTER POLICY profiles_org_isolation ON identity_profiles
    USING (org_id = app_current_org_id())
    WITH CHECK (org_id = app_current_org_id());

ALTER POLICY aliases_org_isolation ON identity_aliases
    USING (org_id = app_current_org_id())
    WITH CHECK (org_id = app_current_org_id());

ALTER POLICY entities_org_isolation ON finance_entities
    USING (org_id = app_current_org_id())
    WITH CHECK (org_id = app_current_org_id());

ALTER POLICY vendors_org_isolation ON vendors
    USING (org_id = app_current_org_id())
    WITH CHECK (org_id = app_current_org_id());

ALTER POLICY customers_org_isolation ON customers
    USING (org_id = app_current_org_id())
    WITH CHECK (org_id = app_current_org_id());

ALTER POLICY invoices_org_isolation ON invoices
    USING (org_id = app_current_org_id())
    WITH CHECK (org_id = app_current_org_id());

ALTER POLICY journals_org_isolation ON journal_entries
    USING (org_id = app_current_org_id())
    WITH CHECK (org_id = app_current_org_id());

ALTER POLICY approvals_org_isolation ON approvals
    USING (org_id = app_current_org_id())
    WITH CHECK (org_id = app_current_org_id());

ALTER POLICY workflows_org_isolation ON workflows
    USING (org_id = app_current_org_id())
    WITH CHECK (org_id = app_current_org_id());

ALTER POLICY workflow_steps_org_isolation ON workflow_steps
    USING (org_id = app_current_org_id())
    WITH CHECK (org_id = app_current_org_id());

ALTER POLICY decisions_org_isolation ON decisions
    USING (org_id = app_current_org_id())
    WITH CHECK (org_id = app_current_org_id());

ALTER POLICY incidents_org_isolation ON incidents
    USING (org_id = app_current_org_id())
    WITH CHECK (org_id = app_current_org_id());

ALTER POLICY memory_org_isolation ON memory_records
    USING (org_id = app_current_org_id())
    WITH CHECK (org_id = app_current_org_id());

ALTER POLICY documents_org_isolation ON documents
    USING (org_id = app_current_org_id())
    WITH CHECK (org_id = app_current_org_id());

ALTER POLICY chunks_org_isolation ON document_chunks
    USING (org_id = app_current_org_id())
    WITH CHECK (org_id = app_current_org_id());

ALTER POLICY citations_org_isolation ON citations
    USING (org_id = app_current_org_id())
    WITH CHECK (org_id = app_current_org_id());

ALTER POLICY agent_runs_org_isolation ON agent_runs
    USING (org_id = app_current_org_id())
    WITH CHECK (org_id = app_current_org_id());

ALTER POLICY agent_actions_org_isolation ON agent_actions
    USING (org_id = app_current_org_id())
    WITH CHECK (org_id = app_current_org_id());

ALTER POLICY audit_org_isolation ON audit_logs
    USING (org_id = app_current_org_id())
    WITH CHECK (org_id = app_current_org_id());

ALTER POLICY qa_gold_examples_org_isolation ON qa_gold_examples
    USING (org_id = app_current_org_id())
    WITH CHECK (org_id = app_current_org_id());

ALTER POLICY retrieval_judgments_org_isolation ON retrieval_judgments
    USING (org_id = app_current_org_id())
    WITH CHECK (org_id = app_current_org_id());

ALTER POLICY safety_events_org_isolation ON safety_events
    USING (org_id = app_current_org_id())
    WITH CHECK (org_id = app_current_org_id());

ALTER POLICY feedback_events_org_isolation ON feedback_events
    USING (org_id = app_current_org_id())
    WITH CHECK (org_id = app_current_org_id());

ALTER POLICY eval_runs_org_isolation ON eval_runs
    USING (org_id = app_current_org_id())
    WITH CHECK (org_id = app_current_org_id());

ALTER POLICY connector_sync_states_org_isolation ON connector_sync_states
    USING (org_id = app_current_org_id())
    WITH CHECK (org_id = app_current_org_id());

ALTER POLICY connector_processed_records_org_isolation ON connector_processed_records
    USING (org_id = app_current_org_id())
    WITH CHECK (org_id = app_current_org_id());
