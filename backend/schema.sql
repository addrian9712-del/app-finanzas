-- App Finanzas - Schema inicial Fase 1

CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  email TEXT,
  display_name TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS card_templates (
  id TEXT PRIMARY KEY,
  type TEXT NOT NULL,
  title TEXT NOT NULL,
  description TEXT,
  icon TEXT,
  color TEXT,
  default_config_json TEXT NOT NULL,
  is_system INTEGER NOT NULL DEFAULT 1,
  version INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_cards (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  template_id TEXT,
  type TEXT NOT NULL,
  title TEXT NOT NULL,
  description TEXT,
  icon TEXT,
  color TEXT,
  config_json TEXT NOT NULL,
  is_active INTEGER NOT NULL DEFAULT 1,
  is_archived INTEGER NOT NULL DEFAULT 0,
  deleted_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS card_instances (
  id TEXT PRIMARY KEY,
  user_card_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  date TEXT NOT NULL,
  status TEXT NOT NULL,
  completion_pct REAL NOT NULL DEFAULT 0,
  notes TEXT,
  completed_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS routine_steps (
  id TEXT PRIMARY KEY,
  user_card_id TEXT NOT NULL,
  position INTEGER NOT NULL,
  title TEXT NOT NULL,
  is_required INTEGER NOT NULL DEFAULT 1,
  estimated_min INTEGER,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS routine_step_logs (
  id TEXT PRIMARY KEY,
  routine_step_id TEXT NOT NULL,
  user_card_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  date TEXT NOT NULL,
  is_done INTEGER NOT NULL DEFAULT 0,
  done_at TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS daily_plan_items (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  date TEXT NOT NULL,
  user_card_id TEXT NOT NULL,
  start_time TEXT,
  end_time TEXT,
  priority INTEGER DEFAULT 2,
  energy_level INTEGER DEFAULT 2,
  calendar_event_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS study_subjects (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  name TEXT NOT NULL,
  color TEXT,
  target_hours_week REAL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS study_sessions (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  subject_id TEXT NOT NULL,
  user_card_id TEXT,
  planned_start TEXT,
  planned_end TEXT,
  actual_min INTEGER DEFAULT 0,
  pomodoros_completed INTEGER DEFAULT 0,
  status TEXT NOT NULL,
  notes TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reminders (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  user_card_id TEXT NOT NULL,
  channel TEXT NOT NULL,
  trigger_at TEXT,
  repeat_rule TEXT,
  is_exact INTEGER NOT NULL DEFAULT 0,
  enabled INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sync_queue (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  entity TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  operation TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  version INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  retry_count INTEGER NOT NULL DEFAULT 0,
  last_error TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sync_state (
  user_id TEXT PRIMARY KEY,
  device_id TEXT NOT NULL,
  last_push_at TEXT,
  last_pull_at TEXT,
  app_version TEXT,
  updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_user_cards_user_active ON user_cards(user_id, is_active, is_archived);
CREATE INDEX IF NOT EXISTS idx_card_instances_user_date ON card_instances(user_id, date);
CREATE INDEX IF NOT EXISTS idx_daily_plan_user_date ON daily_plan_items(user_id, date);
CREATE INDEX IF NOT EXISTS idx_study_sessions_user_status ON study_sessions(user_id, status);
CREATE INDEX IF NOT EXISTS idx_sync_queue_user_status ON sync_queue(user_id, status, created_at);
