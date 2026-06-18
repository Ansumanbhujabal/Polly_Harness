-- L5 Durable State — initial schema
-- Migration: 0001_initial
-- Tables owned by the Repository facade. LangGraph owns its own tables (checkpoints, writes).

CREATE TABLE IF NOT EXISTS refunds (
    refund_id        TEXT    NOT NULL,
    conversation_id  TEXT    NOT NULL,
    order_id         TEXT    NOT NULL,
    customer_id      TEXT    NOT NULL,
    amount_usd       REAL    NOT NULL,
    kind             TEXT    NOT NULL,
    cited_clauses    TEXT    NOT NULL DEFAULT '[]',  -- JSON array
    reasoning        TEXT    NOT NULL DEFAULT '',
    created_at       TEXT    NOT NULL,
    PRIMARY KEY (refund_id),
    UNIQUE (conversation_id, order_id)
);

CREATE TABLE IF NOT EXISTS escalations (
    escalation_id    TEXT    NOT NULL PRIMARY KEY,
    conversation_id  TEXT    NOT NULL,
    reason_code      TEXT    NOT NULL,
    severity         TEXT    NOT NULL DEFAULT 'medium',
    created_at       TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS incidents (
    incident_id         TEXT    NOT NULL PRIMARY KEY,
    conversation_id     TEXT    NOT NULL,
    triggered_by        TEXT    NOT NULL,
    layer               TEXT    NOT NULL,
    summary             TEXT    NOT NULL,
    detail              TEXT    NOT NULL DEFAULT '{}',  -- JSON object
    proposed_remediation TEXT,
    created_at          TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS pending_approvals (
    approval_id             TEXT    NOT NULL PRIMARY KEY,
    conversation_id         TEXT    NOT NULL,
    candidate_decision      TEXT    NOT NULL,  -- JSON (RefundDecision)
    required_approver_role  TEXT    NOT NULL,
    created_at              TEXT    NOT NULL,
    resolution              TEXT,              -- NULL | 'approved' | 'denied'
    approver                TEXT,
    resolved_at             TEXT
);

CREATE TABLE IF NOT EXISTS processed_incidents (
    incident_id  TEXT    NOT NULL PRIMARY KEY,
    processed_at TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS schema_versions (
    version     TEXT    NOT NULL PRIMARY KEY,
    applied_at  TEXT    NOT NULL
);
