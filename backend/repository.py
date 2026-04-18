from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
SCHEMA_PATH = ROOT / "schema.sql"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class Repo:
    def __init__(self, db_path: str = ":memory:") -> None:
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

    def init_schema(self) -> None:
        schema = SCHEMA_PATH.read_text(encoding="utf-8")
        self.conn.executescript(schema)
        self.conn.commit()

    def create_user_card(self, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        card_id = f"uc_{uuid.uuid4().hex[:16]}"
        ts = now_iso()
        row = {
            "id": card_id,
            "user_id": user_id,
            "template_id": payload.get("template_id"),
            "type": payload["type"],
            "title": payload["title"],
            "description": payload.get("description"),
            "icon": payload.get("icon"),
            "color": payload.get("color"),
            "config_json": json.dumps(payload.get("config", {}), ensure_ascii=False),
            "is_active": 1 if payload.get("is_active", True) else 0,
            "is_archived": 1 if payload.get("is_archived", False) else 0,
            "deleted_at": None,
            "created_at": ts,
            "updated_at": ts,
        }
        self.conn.execute(
            """
            INSERT INTO user_cards(
              id,user_id,template_id,type,title,description,icon,color,config_json,
              is_active,is_archived,deleted_at,created_at,updated_at
            ) VALUES (
              :id,:user_id,:template_id,:type,:title,:description,:icon,:color,:config_json,
              :is_active,:is_archived,:deleted_at,:created_at,:updated_at
            )
            """,
            row,
        )
        self.conn.commit()
        return self.get_user_card(user_id, card_id)

    def list_user_cards(self, user_id: str) -> list[dict[str, Any]]:
        cur = self.conn.execute(
            """
            SELECT *
            FROM user_cards
            WHERE user_id = ? AND deleted_at IS NULL
            ORDER BY created_at DESC
            """,
            (user_id,),
        )
        return [self._normalize_card(dict(r)) for r in cur.fetchall()]

    def get_user_card(self, user_id: str, card_id: str) -> dict[str, Any]:
        cur = self.conn.execute(
            "SELECT * FROM user_cards WHERE user_id = ? AND id = ? AND deleted_at IS NULL",
            (user_id, card_id),
        )
        row = cur.fetchone()
        if not row:
            raise KeyError("card_not_found")
        return self._normalize_card(dict(row))

    def update_user_card(self, user_id: str, card_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        card = self.get_user_card(user_id, card_id)
        allowed = {"title", "description", "icon", "color", "is_active", "is_archived", "config"}
        for key in patch:
            if key not in allowed:
                raise ValueError(f"invalid_field:{key}")

        merged_config = patch.get("config", card.get("config", {}))
        updates = {
            "title": patch.get("title", card["title"]),
            "description": patch.get("description", card.get("description")),
            "icon": patch.get("icon", card.get("icon")),
            "color": patch.get("color", card.get("color")),
            "is_active": 1 if patch.get("is_active", card["is_active"]) else 0,
            "is_archived": 1 if patch.get("is_archived", card["is_archived"]) else 0,
            "config_json": json.dumps(merged_config, ensure_ascii=False),
            "updated_at": now_iso(),
            "id": card_id,
            "user_id": user_id,
        }

        self.conn.execute(
            """
            UPDATE user_cards
            SET title=:title, description=:description, icon=:icon, color=:color,
                is_active=:is_active, is_archived=:is_archived, config_json=:config_json,
                updated_at=:updated_at
            WHERE id=:id AND user_id=:user_id AND deleted_at IS NULL
            """,
            updates,
        )
        self.conn.commit()
        return self.get_user_card(user_id, card_id)

    def delete_user_card(self, user_id: str, card_id: str) -> None:
        self.get_user_card(user_id, card_id)
        self.conn.execute(
            "UPDATE user_cards SET deleted_at=?, updated_at=? WHERE id=? AND user_id=?",
            (now_iso(), now_iso(), card_id, user_id),
        )
        self.conn.commit()

    def push_sync_changes(self, user_id: str, changes: list[dict[str, Any]]) -> dict[str, Any]:
        accepted: list[str] = []
        for ch in changes:
            self.conn.execute(
                """
                INSERT INTO sync_queue(id,user_id,entity,entity_id,operation,payload_json,version,status,retry_count,last_error,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    ch["change_id"],
                    user_id,
                    ch["entity"],
                    ch["entity_id"],
                    ch["operation"],
                    json.dumps(ch.get("payload", {}), ensure_ascii=False),
                    int(ch.get("version", 1)),
                    "pending",
                    0,
                    None,
                    now_iso(),
                    now_iso(),
                ),
            )
            accepted.append(ch["change_id"])
        self.conn.commit()
        return {"accepted": accepted, "rejected": []}

    def pull_sync_changes(self, user_id: str, since: str | None = None) -> list[dict[str, Any]]:
        q = "SELECT * FROM sync_queue WHERE user_id = ?"
        params: list[Any] = [user_id]
        if since:
            q += " AND updated_at > ?"
            params.append(since)
        q += " ORDER BY updated_at ASC"

        cur = self.conn.execute(q, tuple(params))
        rows = []
        for r in cur.fetchall():
            d = dict(r)
            rows.append(
                {
                    "change_id": d["id"],
                    "entity": d["entity"],
                    "entity_id": d["entity_id"],
                    "operation": d["operation"],
                    "version": d["version"],
                    "payload": json.loads(d["payload_json"] or "{}"),
                    "updated_at": d["updated_at"],
                }
            )
        return rows

    @staticmethod
    def _normalize_card(row: dict[str, Any]) -> dict[str, Any]:
        row["config"] = json.loads(row.pop("config_json") or "{}")
        row["is_active"] = bool(row["is_active"])
        row["is_archived"] = bool(row["is_archived"])
        return row
