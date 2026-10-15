"""Canonical session snapshots, version checks and search cache in SQLite."""
import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from ..models.schemas import TripPlan, TripRequest


class VersionConflict(ValueError):
    pass


class ConversationStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS conversations (id TEXT PRIMARY KEY, version INTEGER NOT NULL, snapshot TEXT NOT NULL)")
        self._guard = threading.Lock()
        self._locks = {}

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        try:
            with db:
                yield db
        finally:
            db.close()

    def lock(self, session_id):
        with self._guard:
            return self._locks.setdefault(session_id, threading.RLock())

    def create(self, request: TripRequest, plan: TripPlan):
        now = datetime.now(timezone.utc).isoformat()
        data = {"id": str(uuid4()), "title": f"{request.city} · {request.travel_days}日游",
                "version": 1, "created_at": now, "updated_at": now,
                "trip_request": request.model_dump(), "plan": plan.model_dump(),
                "constraints": [], "messages": [{"role": "assistant", "content": "行程已保存。可以继续补充需求、调整指定日期，或查询景点开放与预约信息。", "sources": []}]}
        with self.connect() as db:
            db.execute("INSERT INTO conversations VALUES (?, ?, ?)", (data["id"], 1, json.dumps(data, ensure_ascii=False)))
        return data

    def get(self, session_id):
        with self.connect() as db:
            row = db.execute("SELECT snapshot FROM conversations WHERE id=?", (session_id,)).fetchone()
        if row is None:
            raise KeyError(session_id)
        return json.loads(row[0])

    def list(self):
        with self.connect() as db:
            rows = db.execute("SELECT snapshot FROM conversations ORDER BY rowid DESC LIMIT 100").fetchall()
        return [{k: value[k] for k in ("id", "title", "version", "updated_at")}
                for (raw,) in rows for value in [json.loads(raw)]]

    def save(self, data, expected_version):
        snapshot = {**data, "version": expected_version + 1,
                    "updated_at": datetime.now(timezone.utc).isoformat()}
        with self.connect() as db:
            changed = db.execute("UPDATE conversations SET version=?, snapshot=? WHERE id=? AND version=?",
                                 (snapshot["version"], json.dumps(snapshot, ensure_ascii=False),
                                  snapshot["id"], expected_version)).rowcount
            if changed != 1:
                raise VersionConflict("行程版本已更新，请重新载入会话后再操作。")
        return snapshot
