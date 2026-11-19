CREATE TABLE IF NOT EXISTS inspections (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    equipment_key   TEXT    NOT NULL,
    inspection_date TEXT    NOT NULL,
    inspector       TEXT    NOT NULL DEFAULT '',
    note            TEXT    NOT NULL DEFAULT '',
    created_at      TEXT    NOT NULL,
    updated_at      TEXT,
    editable        INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_inspections_equip_date
    ON inspections(equipment_key, inspection_date);

CREATE TABLE IF NOT EXISTS inspection_items (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    inspection_id INTEGER NOT NULL,
    section       TEXT    NOT NULL DEFAULT '',
    item_name     TEXT    NOT NULL,
    item_type     TEXT    NOT NULL,
    unit          TEXT    NOT NULL DEFAULT '',
    min_value     REAL,
    max_value     REAL,
    value_check   INTEGER,
    value_number  REAL,
    value_before  REAL,
    value_text    TEXT,
    meter_group   TEXT,
    judgement     TEXT    NOT NULL DEFAULT '',
    sort_order    INTEGER NOT NULL DEFAULT 0,
    remark        TEXT    NOT NULL DEFAULT '',
    FOREIGN KEY (inspection_id) REFERENCES inspections(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_inspection_items_inspection_id
    ON inspection_items(inspection_id);

CREATE TABLE IF NOT EXISTS temp_inspections (
    equipment_key TEXT PRIMARY KEY,
    saved_at      TEXT NOT NULL,
    data          TEXT NOT NULL
);
