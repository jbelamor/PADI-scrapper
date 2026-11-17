"""Persistencia en SQLite: usuarios, suscripciones y plazas ya notificadas."""
import sqlite3
from contextlib import contextmanager
from datetime import datetime

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    chat_id    INTEGER PRIMARY KEY,
    name       TEXT,
    lat        REAL,
    lon        REAL,
    address    TEXT,
    radius_km  REAL,
    alerts     INTEGER NOT NULL DEFAULT 1,
    tipos      TEXT NOT NULL DEFAULT 'E',
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS subs (
    chat_id   INTEGER NOT NULL,
    cfunc     TEXT NOT NULL,
    -- 0 = recién añadida: en la próxima comprobación se marcan como vistas
    -- las plazas ya publicadas (para no avisar de golpe de todo lo antiguo)
    baselined INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (chat_id, cfunc)
);
CREATE TABLE IF NOT EXISTS seen (
    chat_id  INTEGER NOT NULL,
    id_susti INTEGER NOT NULL,
    seen_at  TEXT,
    PRIMARY KEY (chat_id, id_susti)
);
CREATE TABLE IF NOT EXISTS catalog_extra (
    cfunc  TEXT PRIMARY KEY,
    cuerpo TEXT,
    name   TEXT
);
CREATE TABLE IF NOT EXISTS geocache (
    ccentro TEXT PRIMARY KEY,
    lat     REAL,
    lon     REAL
);
"""


class Storage:
    def __init__(self, path):
        self.path = path
        with self._conn() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # ---------- usuarios ----------
    def ensure_user(self, chat_id, name=None):
        with self._conn() as c:
            c.execute("INSERT OR IGNORE INTO users (chat_id, name, created_at) VALUES (?, ?, ?)",
                      (chat_id, name, datetime.now().isoformat(timespec="seconds")))
            if name:
                c.execute("UPDATE users SET name = ? WHERE chat_id = ?", (name, chat_id))

    def get_user(self, chat_id):
        with self._conn() as c:
            row = c.execute("SELECT * FROM users WHERE chat_id = ?", (chat_id,)).fetchone()
            return dict(row) if row else None

    def all_users(self, only_alerts=False):
        q = "SELECT * FROM users"
        if only_alerts:
            q += " WHERE alerts = 1"
        with self._conn() as c:
            return [dict(r) for r in c.execute(q)]

    def set_location(self, chat_id, lat, lon, address):
        with self._conn() as c:
            c.execute("UPDATE users SET lat = ?, lon = ?, address = ? WHERE chat_id = ?",
                      (lat, lon, address, chat_id))

    def clear_location(self, chat_id):
        with self._conn() as c:
            c.execute("UPDATE users SET lat = NULL, lon = NULL, address = NULL, radius_km = NULL "
                      "WHERE chat_id = ?", (chat_id,))

    def set_radius(self, chat_id, km):
        with self._conn() as c:
            c.execute("UPDATE users SET radius_km = ? WHERE chat_id = ?", (km, chat_id))

    def set_alerts(self, chat_id, on):
        with self._conn() as c:
            c.execute("UPDATE users SET alerts = ? WHERE chat_id = ?", (1 if on else 0, chat_id))

    def set_tipos(self, chat_id, tipos):
        with self._conn() as c:
            c.execute("UPDATE users SET tipos = ? WHERE chat_id = ?", (tipos, chat_id))

    def delete_user(self, chat_id):
        with self._conn() as c:
            for table in ("subs", "seen", "users"):
                c.execute(f"DELETE FROM {table} WHERE chat_id = ?", (chat_id,))

    # ---------- suscripciones ----------
    def subs(self, chat_id):
        with self._conn() as c:
            return [r["cfunc"] for r in
                    c.execute("SELECT cfunc FROM subs WHERE chat_id = ? ORDER BY cfunc", (chat_id,))]

    def toggle_sub(self, chat_id, cfunc):
        """Añade o quita la suscripción. Devuelve True si queda suscrito."""
        with self._conn() as c:
            cur = c.execute("DELETE FROM subs WHERE chat_id = ? AND cfunc = ?", (chat_id, cfunc))
            if cur.rowcount:
                return False
            c.execute("INSERT INTO subs (chat_id, cfunc) VALUES (?, ?)", (chat_id, cfunc))
            return True

    def add_sub(self, chat_id, cfunc):
        with self._conn() as c:
            c.execute("INSERT OR IGNORE INTO subs (chat_id, cfunc) VALUES (?, ?)", (chat_id, cfunc))

    def clear_subs(self, chat_id):
        with self._conn() as c:
            c.execute("DELETE FROM subs WHERE chat_id = ?", (chat_id,))

    def subs_full(self, chat_id):
        """[(cfunc, baselined)]"""
        with self._conn() as c:
            return [(r["cfunc"], bool(r["baselined"])) for r in c.execute(
                "SELECT cfunc, baselined FROM subs WHERE chat_id = ?", (chat_id,))]

    def set_baselined(self, chat_id, cfuncs):
        with self._conn() as c:
            c.executemany("UPDATE subs SET baselined = 1 WHERE chat_id = ? AND cfunc = ?",
                          [(chat_id, cf) for cf in cfuncs])

    # ---------- plazas vistas ----------
    def seen_ids(self, chat_id):
        with self._conn() as c:
            return {r["id_susti"] for r in
                    c.execute("SELECT id_susti FROM seen WHERE chat_id = ?", (chat_id,))}

    def mark_seen(self, chat_id, ids):
        now = datetime.now().isoformat(timespec="seconds")
        with self._conn() as c:
            c.executemany("INSERT OR IGNORE INTO seen (chat_id, id_susti, seen_at) VALUES (?, ?, ?)",
                          [(chat_id, i, now) for i in ids])

    # ---------- catálogo dinámico ----------
    def catalog_extra(self):
        with self._conn() as c:
            return {r["cfunc"]: {"cuerpo": r["cuerpo"], "name": r["name"]}
                    for r in c.execute("SELECT * FROM catalog_extra")}

    def add_catalog(self, entries):
        with self._conn() as c:
            c.executemany("INSERT OR REPLACE INTO catalog_extra (cfunc, cuerpo, name) VALUES (?, ?, ?)",
                          [(k, v["cuerpo"], v["name"]) for k, v in entries.items()])

    # ---------- caché de geocodificación de centros ----------
    def geocache_get(self, ccentro):
        with self._conn() as c:
            r = c.execute("SELECT lat, lon FROM geocache WHERE ccentro = ?", (ccentro,)).fetchone()
            return (r["lat"], r["lon"]) if r else None

    def geocache_set(self, ccentro, lat, lon):
        with self._conn() as c:
            c.execute("INSERT OR REPLACE INTO geocache (ccentro, lat, lon) VALUES (?, ?, ?)",
                      (ccentro, lat, lon))
