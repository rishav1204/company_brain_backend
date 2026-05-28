-- Module 5: Notification & Communication Engine

CREATE SCHEMA IF NOT EXISTS notifications;

CREATE TABLE IF NOT EXISTS notifications.notifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
    notification_type VARCHAR(64) NOT NULL,
    channel VARCHAR(32) NOT NULL,
    recipient_user_id UUID,
    recipient_address TEXT,
    subject VARCHAR(512),
    body TEXT NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    priority VARCHAR(16) NOT NULL DEFAULT 'medium',
    related_entity_type VARCHAR(64),
    related_entity_id UUID,
    event_type VARCHAR(128),
    event_id UUID,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    acknowledged_at TIMESTAMPTZ,
    snoozed_until TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sent_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS notifications_org_status_idx
    ON notifications.notifications (org_id, status, created_at DESC);

CREATE INDEX IF NOT EXISTS notifications_recipient_unread_idx
    ON notifications.notifications (org_id, recipient_user_id, created_at DESC)
    WHERE acknowledged_at IS NULL;

CREATE TABLE IF NOT EXISTS notifications.delivery_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
    notification_id UUID NOT NULL REFERENCES notifications.notifications(id) ON DELETE CASCADE,
    provider VARCHAR(64) NOT NULL,
    delivery_status VARCHAR(32) NOT NULL,
    provider_response JSONB NOT NULL DEFAULT '{}'::jsonb,
    attempt_count INT NOT NULL DEFAULT 0,
    last_attempt_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS notifications_delivery_notification_idx
    ON notifications.delivery_logs (notification_id, created_at DESC);

CREATE TABLE IF NOT EXISTS notifications.templates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID REFERENCES core.organizations(id) ON DELETE CASCADE,
    template_key VARCHAR(128) NOT NULL,
    channel VARCHAR(32) NOT NULL,
    subject_template TEXT,
    body_template TEXT NOT NULL,
    variables JSONB NOT NULL DEFAULT '[]'::jsonb,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (org_id, template_key, channel)
);

CREATE TABLE IF NOT EXISTS notifications.preferences (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL,
    channel VARCHAR(32) NOT NULL,
    notification_type VARCHAR(64) NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    quiet_hours JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (org_id, user_id, channel, notification_type)
);

CREATE TABLE IF NOT EXISTS notifications.subscriptions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL,
    channel_key VARCHAR(128) NOT NULL,
    subscription_type VARCHAR(64) NOT NULL DEFAULT 'realtime',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (org_id, user_id, channel_key)
);

CREATE TABLE IF NOT EXISTS notifications.digest_queue (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL,
    digest_type VARCHAR(64) NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    scheduled_for DATE NOT NULL DEFAULT CURRENT_DATE,
    processed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS notifications_digest_pending_idx
    ON notifications.digest_queue (org_id, scheduled_for, processed)
    WHERE processed = FALSE;

ALTER TABLE notifications.notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications.notifications FORCE ROW LEVEL SECURITY;
ALTER TABLE notifications.delivery_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications.delivery_logs FORCE ROW LEVEL SECURITY;
ALTER TABLE notifications.templates ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications.templates FORCE ROW LEVEL SECURITY;
ALTER TABLE notifications.preferences ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications.preferences FORCE ROW LEVEL SECURITY;
ALTER TABLE notifications.subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications.subscriptions FORCE ROW LEVEL SECURITY;
ALTER TABLE notifications.digest_queue ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications.digest_queue FORCE ROW LEVEL SECURITY;

CREATE POLICY notifications_rows_org ON notifications.notifications
    USING (org_id = current_setting('app.current_org', true)::UUID);
CREATE POLICY notifications_delivery_org ON notifications.delivery_logs
    USING (org_id = current_setting('app.current_org', true)::UUID);
CREATE POLICY notifications_templates_org ON notifications.templates
    USING (org_id IS NULL OR org_id = current_setting('app.current_org', true)::UUID);
CREATE POLICY notifications_preferences_org ON notifications.preferences
    USING (org_id = current_setting('app.current_org', true)::UUID);
CREATE POLICY notifications_subscriptions_org ON notifications.subscriptions
    USING (org_id = current_setting('app.current_org', true)::UUID);
CREATE POLICY notifications_digest_org ON notifications.digest_queue
    USING (org_id = current_setting('app.current_org', true)::UUID);

-- Seed global templates (org_id NULL = platform default)
INSERT INTO notifications.templates (org_id, template_key, channel, subject_template, body_template, variables)
VALUES
    (NULL, 'approval_request', 'email', 'Approval required: {{entity_label}}',
     'Hi {{recipient_name}},\n\nPlease approve {{entity_label}} ({{amount}}).\n\nOpen Action Center to review.',
     '["recipient_name","entity_label","amount"]'::jsonb),
    (NULL, 'approval_request', 'in_app', NULL,
     'Approval required: {{entity_label}}',
     '["entity_label","amount"]'::jsonb),
    (NULL, 'sla_breach', 'email', 'SLA breach: {{workflow_id}}',
     'Workflow {{workflow_id}} breached SLA. Escalation may be required.',
     '["workflow_id"]'::jsonb),
    (NULL, 'compliance_alert', 'in_app', NULL,
     'Compliance: {{compliance_type}} — {{status}}',
     '["compliance_type","status"]'::jsonb),
    (NULL, 'risk_alert', 'in_app', NULL,
     'Risk alert: {{summary}}',
     '["summary"]'::jsonb),
    (NULL, 'workflow_escalation', 'email', 'Escalation: {{workflow_id}}',
     'Workflow {{workflow_id}} was escalated. Reason: {{reason}}',
     '["workflow_id","reason"]'::jsonb)
ON CONFLICT DO NOTHING;
