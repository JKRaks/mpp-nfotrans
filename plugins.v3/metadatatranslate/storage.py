"""Independent paged cache/history; credentials are not stored in SQLite."""
import json
import os
import sqlite3
import tempfile
import threading
import time
from pathlib import Path


def atomic_json(path, value):
    path = Path(path)
    fd, tmp = tempfile.mkstemp(prefix=".translate-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False)
            stream.flush(); os.fsync(stream.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


class Storage:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.history_days, self.prune_after = 30, 0
        self.db = sqlite3.connect(str(self.directory / "translation.sqlite3"), check_same_thread=False)
        with self.db:
            self.db.execute("PRAGMA journal_mode=WAL")
            self.db.execute("CREATE TABLE IF NOT EXISTS cache (kind TEXT, key TEXT, expires REAL, value TEXT, PRIMARY KEY(kind,key))")
            self.db.execute("CREATE INDEX IF NOT EXISTS cache_expiry ON cache(expires)")
            self.db.execute("CREATE TABLE IF NOT EXISTS calls (id INTEGER PRIMARY KEY, created REAL, provider TEXT, status TEXT, summary TEXT, detail TEXT)")
            self.db.execute("CREATE INDEX IF NOT EXISTS calls_created ON calls(created)")

    def secrets(self):
        path = self.directory / "secrets.json"
        return json.loads(path.read_text()) if path.exists() else {}

    def save_secrets(self, changes):
        with self.lock:
            values = self.secrets()
            for key, value in changes.items():
                if value is None: values.pop(key, None)
                elif value: values[key] = value
            atomic_json(self.directory / "secrets.json", values)

    def get(self, kind, key):
        with self.lock:
            row = self.db.execute("SELECT value FROM cache WHERE kind=? AND key=? AND expires>?", (kind, key, time.time())).fetchone()
            return json.loads(row[0]) if row else None

    def put(self, kind, key, value, seconds):
        with self.lock, self.db:
            self.db.execute("INSERT OR REPLACE INTO cache VALUES (?,?,?,?)", (kind, key, time.time() + seconds, json.dumps(value, ensure_ascii=False)))

    def record(self, provider, status, summary, detail):
        with self.lock, self.db:
            if time.time() >= self.prune_after: self.prune(self.history_days)
            cursor = self.db.execute("INSERT INTO calls(created,provider,status,summary,detail) VALUES (?,?,?,?,?)",
                                     (time.time(), provider, status, summary, json.dumps(detail, ensure_ascii=False)))
            return cursor.lastrowid

    def history(self, page=1, page_size=30, status="", provider=""):
        page, page_size = max(1, page), min(100, max(1, page_size))
        clauses, args = [], []
        for key, value in [("status", status), ("provider", provider)]:
            if value: clauses.append(key + "=?"); args.append(value)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self.lock:
            if time.time() >= self.prune_after: self.prune(self.history_days)
            total = self.db.execute("SELECT count(*) FROM calls" + where, args).fetchone()[0]
            rows = self.db.execute("SELECT id,created,provider,status,summary FROM calls" + where + " ORDER BY id DESC LIMIT ? OFFSET ?", args + [page_size, (page - 1) * page_size]).fetchall()
        return {"items": [dict(zip(["id", "created", "provider", "status", "summary"], r)) for r in rows], "total": total, "page": page, "page_size": page_size}

    def detail(self, id):
        with self.lock:
            row = self.db.execute("SELECT detail FROM calls WHERE id=?", (id,)).fetchone()
            return json.loads(row[0]) if row else None

    def delete_calls(self, ids):
        with self.lock, self.db:
            self.db.executemany("DELETE FROM calls WHERE id=?", [(i,) for i in ids])

    def stats(self):
        with self.lock:
            return dict(self.db.execute("SELECT kind,count(*) FROM cache WHERE expires>? GROUP BY kind", (time.time(),)).fetchall())

    def clear(self, kind):
        if kind not in {"source", "translation", "all"}: raise ValueError("缓存类型无效")
        with self.lock, self.db:
            if kind == "all": self.db.execute("DELETE FROM cache")
            else: self.db.execute("DELETE FROM cache WHERE kind=?", (kind,))

    def prune(self, history_days):
        with self.lock, self.db:
            self.db.execute("DELETE FROM cache WHERE expires<?", (time.time(),))
            self.db.execute("DELETE FROM calls WHERE created<?", (time.time() - history_days * 86400,))
            self.history_days, self.prune_after = history_days, time.time() + 3600

    def close(self):
        with self.lock: self.db.close()
