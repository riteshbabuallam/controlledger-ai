SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS claims (
  claim_id TEXT PRIMARY KEY,
  submission_json TEXT NOT NULL,
  submitted_at TEXT NOT NULL,
  status TEXT NOT NULL,
  recommendation TEXT,
  risk_score INTEGER,
  review_status TEXT NOT NULL DEFAULT 'not_required',
  final_decision TEXT,
  reviewer TEXT,
  override_reason TEXT,
  reviewed_at TEXT,
  state_json TEXT,
  passport_json TEXT
);

CREATE TABLE IF NOT EXISTS policies (
  policy_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  version TEXT NOT NULL,
  effective_date TEXT NOT NULL,
  category TEXT NOT NULL,
  jurisdiction TEXT NOT NULL,
  content TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_events (
  event_id INTEGER PRIMARY KEY AUTOINCREMENT,
  claim_id TEXT,
  event_type TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS final_decisions (
  claim_id TEXT PRIMARY KEY,
  decision TEXT NOT NULL,
  reviewer TEXT NOT NULL,
  override_reason TEXT,
  authorized INTEGER NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS simulations (
  simulation_id TEXT PRIMARY KEY,
  request_json TEXT NOT NULL,
  result_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS passport_revisions (
  claim_id TEXT NOT NULL,
  revision INTEGER NOT NULL,
  passport_json TEXT NOT NULL,
  reason TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (claim_id, revision)
);

CREATE TABLE IF NOT EXISTS control_drafts (
  draft_id TEXT PRIMARY KEY,
  policy_id TEXT NOT NULL,
  draft_json TEXT NOT NULL,
  status TEXT NOT NULL,
  reviewer TEXT,
  created_at TEXT NOT NULL,
  approved_at TEXT
);
"""
