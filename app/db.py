import os, sqlite3
from flask import current_app, g

SCHEMA_SQL = r"""
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL CHECK(role IN ('admin','manager','staff')),
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS products (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  sku TEXT UNIQUE,
  name TEXT NOT NULL,
  cost REAL NOT NULL DEFAULT 0,
  sell_price REAL NOT NULL DEFAULT 0,
  note TEXT NOT NULL DEFAULT '',
  low_stock_enabled INTEGER NOT NULL DEFAULT 0,
  low_stock_threshold REAL NOT NULL DEFAULT 0,
  email_enabled INTEGER NOT NULL DEFAULT 0,
  is_active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS stock_moves (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  product_id INTEGER NOT NULL,
  move_type TEXT NOT NULL CHECK(move_type IN ('IN','OUT','ADJUST')),
  qty REAL NOT NULL,
  unit_cost REAL,
  unit_price REAL,
  ref_type TEXT NOT NULL DEFAULT '',
  ref_id INTEGER,
  note TEXT NOT NULL DEFAULT '',
  created_by INTEGER,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE,
  FOREIGN KEY(created_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS sales (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  code TEXT NOT NULL UNIQUE,
  customer_note TEXT NOT NULL DEFAULT '',
  shipping_cost REAL NOT NULL DEFAULT 0,
  commission REAL NOT NULL DEFAULT 0,
  other_cost REAL NOT NULL DEFAULT 0,
  other_cost_note TEXT NOT NULL DEFAULT '',
  created_by INTEGER,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY(created_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS sale_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  sale_id INTEGER NOT NULL,
  product_id INTEGER NOT NULL,
  product_name TEXT NOT NULL,
  qty REAL NOT NULL,
  unit_cost REAL NOT NULL,
  unit_price REAL NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY(sale_id) REFERENCES sales(id) ON DELETE CASCADE,
  FOREIGN KEY(product_id) REFERENCES products(id)
);

CREATE TABLE IF NOT EXISTS audit_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  actor_user_id INTEGER,
  action TEXT NOT NULL,            -- e.g. PRODUCT_UPDATE, PRODUCT_DEACTIVATE, STOCK_IN, ...
  entity_type TEXT NOT NULL,       -- e.g. product, sale, setting
  entity_id INTEGER,
  detail TEXT NOT NULL DEFAULT '', -- JSON-ish text
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY(actor_user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS settings (
  id INTEGER PRIMARY KEY CHECK(id=1),
  smtp_host TEXT NOT NULL DEFAULT 'smtp.gmail.com',
  smtp_port INTEGER NOT NULL DEFAULT 587,
  smtp_email TEXT NOT NULL DEFAULT '',
  smtp_pass TEXT NOT NULL DEFAULT '',
  receive_email TEXT NOT NULL DEFAULT '',
  banner_b64 TEXT NOT NULL DEFAULT '',
  banner_path TEXT NOT NULL DEFAULT '',

  theme_primary TEXT NOT NULL DEFAULT '#0d6efd',
  theme_section_bg TEXT NOT NULL DEFAULT '#f8f9fa',
  theme_section_border TEXT NOT NULL DEFAULT '#e9ecef'
);

INSERT OR IGNORE INTO settings(id) VALUES (1);
"""

def _db_path(app):
    os.makedirs(app.instance_path, exist_ok=True)
    return os.path.join(app.instance_path, "storage.db")

def _table_columns(db, table: str) -> set[str]:
    rows = db.execute(f"PRAGMA table_info({table})").fetchall()
    return {r["name"] for r in rows}

def _ensure_products_migrations(db):
    cols = _table_columns(db, "products")
    if "sell_price" not in cols:
        db.execute("ALTER TABLE products ADD COLUMN sell_price REAL NOT NULL DEFAULT 0")
    if "low_stock_enabled" not in cols:
        db.execute("ALTER TABLE products ADD COLUMN low_stock_enabled INTEGER NOT NULL DEFAULT 0")
    if "low_stock_threshold" not in cols:
        db.execute("ALTER TABLE products ADD COLUMN low_stock_threshold REAL NOT NULL DEFAULT 0")
    if "email_enabled" not in cols:
        db.execute("ALTER TABLE products ADD COLUMN email_enabled INTEGER NOT NULL DEFAULT 0")
    if "is_active" not in cols:
        db.execute("ALTER TABLE products ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1")

def _ensure_settings_migrations(db):
    cols = _table_columns(db, "settings")
    if "theme_primary" not in cols:
        db.execute("ALTER TABLE settings ADD COLUMN theme_primary TEXT NOT NULL DEFAULT '#0d6efd'")
    if "theme_section_bg" not in cols:
        db.execute("ALTER TABLE settings ADD COLUMN theme_section_bg TEXT NOT NULL DEFAULT '#f8f9fa'")
    if "theme_section_border" not in cols:
        db.execute("ALTER TABLE settings ADD COLUMN theme_section_border TEXT NOT NULL DEFAULT '#e9ecef'")
    if "banner_path" not in cols:
        db.execute("ALTER TABLE settings ADD COLUMN banner_path TEXT NOT NULL DEFAULT ''")

def _ensure_audit_logs_table(db):
    db.execute(
        """CREATE TABLE IF NOT EXISTS audit_logs (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          actor_user_id INTEGER,
          action TEXT NOT NULL,
          entity_type TEXT NOT NULL,
          entity_id INTEGER,
          detail TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL DEFAULT (datetime('now')),
          FOREIGN KEY(actor_user_id) REFERENCES users(id)
        );"""
    )

def get_db():
    if "db" not in g:
        conn = sqlite3.connect(_db_path(current_app))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        g.db = conn
    return g.db

def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db(app):
    @app.before_request
    def _ensure_schema():
        db = get_db()
        db.executescript(SCHEMA_SQL)

        # Lightweight migrations for existing databases
        _ensure_products_migrations(db)
        _ensure_settings_migrations(db)
        _ensure_audit_logs_table(db)

        db.commit()

        row = db.execute("SELECT COUNT(*) AS c FROM users").fetchone()
        if row["c"] == 0:
            from .auth import hash_password
            db.execute(
                "INSERT INTO users(username,password_hash,role) VALUES (?,?,?)",
                ("admin", hash_password("admin"), "admin"),
            )
            db.commit()

    app.teardown_appcontext(close_db)