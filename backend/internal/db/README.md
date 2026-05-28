# Database Module

This module owns:
- PostgreSQL transactional schema
- pgvector-based semantic retrieval storage
- row-level security policies (`org_id` scoped)
- migration lifecycle

Use `../../migrations/001_init.sql` as the baseline schema.
