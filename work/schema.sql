CREATE TABLE IF NOT EXISTS records (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT    NOT NULL DEFAULT '',
    record_date  TEXT    NOT NULL,
    created_at   TEXT    NOT NULL,
    finalized    INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS entries (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id    INTEGER NOT NULL,
    time_text    TEXT    NOT NULL,
    content      TEXT    NOT NULL,
    is_important INTEGER NOT NULL DEFAULT 0,
    sort_order   REAL    NOT NULL DEFAULT 0,
    created_at   TEXT    NOT NULL,
    updated_at   TEXT,
    FOREIGN KEY (record_id) REFERENCES records(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_entries_record_id ON entries(record_id);

CREATE TABLE IF NOT EXISTS record_photos (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id     INTEGER NOT NULL,
    filename      TEXT    NOT NULL,
    original_name TEXT    NOT NULL DEFAULT '',
    memo          TEXT    NOT NULL DEFAULT '',
    created_at    TEXT    NOT NULL,
    FOREIGN KEY (record_id) REFERENCES records(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_record_photos_record_id ON record_photos(record_id);

CREATE TABLE IF NOT EXISTS button_groups (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    sort_order  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS buttons (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id    INTEGER NOT NULL,
    label       TEXT    NOT NULL,
    is_pinned   INTEGER NOT NULL DEFAULT 0,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (group_id) REFERENCES button_groups(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_buttons_group_id ON buttons(group_id);

-- 運転マニュアル（手順表）の進捗。記録ごと・マニュアルごとに「どの手順を実施したか」を持つ。
-- step_key はマニュアルCSVの「作業内容」（各行で一意）。
CREATE TABLE IF NOT EXISTS manual_progress (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id   INTEGER NOT NULL,
    manual_file TEXT    NOT NULL,
    step_key    TEXT    NOT NULL,
    done_time   TEXT    NOT NULL DEFAULT '',
    entry_id    INTEGER,
    updated_at  TEXT    NOT NULL,
    FOREIGN KEY (record_id) REFERENCES records(id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_manual_progress_step
    ON manual_progress(record_id, manual_file, step_key);
