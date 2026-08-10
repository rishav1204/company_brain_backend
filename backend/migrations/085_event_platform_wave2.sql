-- Phase 1 Wave 2: Event platform hardening (outbox governance + metadata)

-- Outbox status lifecycle: pending|publishing|published|failed|dead|archived
ALTER TABLE platform.event_outbox
    ADD COLUMN IF NOT EXISTS event_type varchar(256) NULL,
    ADD COLUMN IF NOT EXISTS event_version varchar(32) NULL DEFAULT 'v1',
    ADD COLUMN IF NOT EXISTS correlation_id varchar(128) NULL,
    ADD COLUMN IF NOT EXISTS request_id varchar(128) NULL,
    ADD COLUMN IF NOT EXISTS company_id varchar(128) NULL,
    ADD COLUMN IF NOT EXISTS actor_id varchar(128) NULL,
    ADD COLUMN IF NOT EXISTS partition_key varchar(256) NULL,
    ADD COLUMN IF NOT EXISTS ordering_key varchar(256) NULL,
    ADD COLUMN IF NOT EXISTS payload_checksum varchar(64) NULL,
    ADD COLUMN IF NOT EXISTS is_financial boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS failure_class varchar(64) NULL,
    ADD COLUMN IF NOT EXISTS archived_at timestamptz NULL,
    ADD COLUMN IF NOT EXISTS dead_at timestamptz NULL;

CREATE INDEX IF NOT EXISTS idx_platform_event_outbox_dead
    ON platform.event_outbox (status, dead_at DESC)
    WHERE status = 'dead';

CREATE INDEX IF NOT EXISTS idx_platform_event_outbox_financial_pending
    ON platform.event_outbox (is_financial, status, next_attempt_at, created_at)
    WHERE status IN ('pending', 'failed', 'publishing');

CREATE INDEX IF NOT EXISTS idx_platform_event_outbox_correlation
    ON platform.event_outbox (org_id, correlation_id)
    WHERE correlation_id IS NOT NULL;

COMMENT ON COLUMN platform.event_outbox.status IS
    'pending|publishing|published|failed|dead|archived';
