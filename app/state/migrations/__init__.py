"""SQLite migration files for the Durable State layer (L5).

Migrations are plain SQL files applied in lexicographic order by runner.apply_all().
Each applied migration is recorded in schema_versions to ensure idempotency.
"""
