# IAM OIDC Setup

Generic OIDC works with Azure AD, Google Workspace, Okta, and Keycloak.

## Redirect URIs

Register these callback URLs with your IdP:

- Production: `https://<api-host>/iam/auth/oidc/callback`
- Legacy route: `https://<api-host>/auth/oidc/callback`

## Required environment variables

```env
OIDC_ENABLED=true
OIDC_PROVIDER=azure|google|okta|keycloak
OIDC_CLIENT_ID=
OIDC_CLIENT_SECRET=
OIDC_AUTHORIZATION_ENDPOINT=
OIDC_TOKEN_ENDPOINT=
OIDC_JWKS_URL=
OIDC_ISSUER=
OIDC_REDIRECT_URI=
OIDC_ALLOWED_REDIRECT_URIS=https://app.example.com/callback
OIDC_ORG_CLAIM=org_id
OIDC_USER_CLAIM=sub
OIDC_ROLES_CLAIM=roles
```

## Claim mapping

- `OIDC_ORG_CLAIM` — must resolve to a `core.organizations.id` UUID (or enable JIT provisioning).
- `OIDC_USER_CLAIM` — defaults to `sub`; linked via `core.users.idp_subject`.
- `OIDC_ROLES_CLAIM` — optional; IAM DB roles take precedence when `IAM_USE_DB_AUTH=true`.

## JIT provisioning

```env
OIDC_JIT_PROVISIONING_ENABLED=true
OIDC_JIT_DEFAULT_ROLE=viewer
```

Users are created on first login when email domain matches an existing org.

## Sessions

OIDC callback creates a `core.sessions` row with refresh rotation (same as password login).
