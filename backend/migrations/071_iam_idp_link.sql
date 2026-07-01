-- Link IdP subjects to core.users for unified OIDC + password auth.

ALTER TABLE core.users
    ADD COLUMN IF NOT EXISTS idp_subject TEXT,
    ADD COLUMN IF NOT EXISTS idp_provider TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS core_users_idp_provider_subject_key
    ON core.users (idp_provider, idp_subject)
    WHERE idp_subject IS NOT NULL AND idp_provider IS NOT NULL;

CREATE INDEX IF NOT EXISTS core_users_idp_subject_idx ON core.users (idp_subject)
    WHERE idp_subject IS NOT NULL;
