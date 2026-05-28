# API Module

Owns REST APIs under `/api/v1`.

Contract guarantees:
- every response includes `request_id`
- AI-generated responses include `citations[]`, `confidence`, and `verification_status`
- tenant and role checks are applied before context retrieval
