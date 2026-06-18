-- L5 Durable State — add batch_id to processed_incidents
-- Migration: 0002_processed_incidents_batch_id
--
-- The distiller groups each run under a batch_id so proposals can be
-- traced back to a specific distillation run. The column is optional
-- (NOT NULL DEFAULT '') to preserve backward-compat with rows written
-- before this migration.

ALTER TABLE processed_incidents ADD COLUMN batch_id TEXT NOT NULL DEFAULT '';
