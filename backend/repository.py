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
        self.seed_default_templates()
        self.conn.commit()

    def seed_default_templates(self) -> None:
        cur = self.conn.execute("SELECT COUNT(*) AS c FROM card_templates")
        count = int(cur.fetchone()["c"])
        if count > 0:
            return

        ts = now_iso()
        templates = [
            {
                "id": "tpl_water_8",
                "type": "routine",
                "title": "Tomar agua",
                "description": "8 vasos diarios",
                "icon": "💧",
                "color": "#56CFE1",
                "default_config_json": json.dumps({"target": {"unit": "glasses", "value": 8}, "frequency": {"kind": "daily"}}),
                "is_system": 1,
                "version": 1,
                "created_at": ts,
            },
            {
                "id": "tpl_gym",
                "type": "routine",
                "title": "Ir al gym",
                "description": "Rutina de entrenamiento",
                "icon": "🏋️",
                "color": "#7C6FFF",
                "default_config_json": json.dumps({"frequency": {"kind": "weekly_n", "times": 4}}),
                "is_system": 1,
                "version": 1,
                "created_at": ts,
            },
            {
                "id": "tpl_study_pomodoro",
                "type": "study",
                "title": "Pomodoro estudio",
                "description": "2 sesiones de enfoque",
                "icon": "📚",
                "color": "#F5A623",
                "default_config_json": json.dumps({"pomodoro": {"focus_min": 25, "break_min": 5}, "target_sessions": 2}),
                "is_system": 1,
                "version": 1,
                "created_at": ts,
            },
            {
                "id": "tpl_daily_plan",
                "type": "task",
                "title": "Plan del día",
                "description": "Top 3 prioridades",
                "icon": "✅",
                "color": "#5CD679",
                "default_config_json": json.dumps({"frequency": {"kind": "daily"}, "target_items": 3}),
                "is_system": 1,
                "version": 1,
                "created_at": ts,
            },
        ]
        self.conn.executemany(
            """
            INSERT INTO card_templates(id,type,title,description,icon,color,default_config_json,is_system,version,created_at)
            VALUES(:id,:type,:title,:description,:icon,:color,:default_config_json,:is_system,:version,:created_at)
            """,
            templates,
        )

    def list_card_templates(self, type_filter: str | None = None) -> list[dict[str, Any]]:
        q = "SELECT * FROM card_templates"
        params: list[Any] = []
        if type_filter:
            q += " WHERE type = ?"
            params.append(type_filter)
        q += " ORDER BY title ASC"
        cur = self.conn.execute(q, tuple(params))
        rows = []
        for r in cur.fetchall():
            d = dict(r)
            d["default_config"] = json.loads(d.pop("default_config_json") or "{}")
            d["is_system"] = bool(d["is_system"])
            rows.append(d)
        return rows

    def create_user_card(self, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        allowed_types = {"task", "routine", "goal", "study"}
        card_type = str(payload["type"])
        if card_type not in allowed_types:
            raise ValueError("invalid_type")
        title = str(payload["title"]).strip()
        if not title:
            raise ValueError("title_required")
        card_id = f"uc_{uuid.uuid4().hex[:16]}"
        ts = now_iso()
        row = {
            "id": card_id,
            "user_id": user_id,
            "template_id": payload.get("template_id"),
            "type": card_type,
            "title": title,
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
        rejected: list[dict[str, str]] = []
        for ch in changes:
            change_id = str(ch.get("change_id", ""))
            if not change_id:
                rejected.append({"change_id": "", "reason": "change_id_required"})
                continue
            try:
                self.conn.execute(
                    """
                    INSERT INTO sync_queue(id,user_id,entity,entity_id,operation,payload_json,version,status,retry_count,last_error,created_at,updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        change_id,
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
                accepted.append(change_id)
            except sqlite3.IntegrityError:
                cur = self.conn.execute("SELECT user_id FROM sync_queue WHERE id = ?", (change_id,))
                row = cur.fetchone()
                if row and row["user_id"] == user_id:
                    # idempotency: already inserted for this same user
                    accepted.append(change_id)
                else:
                    rejected.append({"change_id": change_id, "reason": "duplicate_change_id"})
        self.conn.commit()
        return {"accepted": accepted, "rejected": rejected}

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

    def list_pending_sync_changes(self, user_id: str, limit: int = 50, max_retry: int = 5) -> list[dict[str, Any]]:
        cur = self.conn.execute(
            """
            SELECT *
            FROM sync_queue
            WHERE user_id = ? AND status IN ('pending', 'failed') AND retry_count < ?
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (user_id, max_retry, limit),
        )
        return [dict(r) for r in cur.fetchall()]

    def mark_sync_change_status(self, change_id: str, status: str, error: str | None = None, bump_retry: bool = False) -> None:
        if bump_retry:
            self.conn.execute(
                """
                UPDATE sync_queue
                SET status = ?, retry_count = retry_count + 1, last_error = ?, updated_at = ?
                WHERE id = ?
                """,
                (status, error, now_iso(), change_id),
            )
        else:
            self.conn.execute(
                """
                UPDATE sync_queue
                SET status = ?, last_error = ?, updated_at = ?
                WHERE id = ?
                """,
                (status, error, now_iso(), change_id),
            )
        self.conn.commit()

    def generate_daily_instances(self, user_id: str, date: str) -> int:
        cards = self.list_user_cards(user_id)
        created = 0
        for card in cards:
            cur = self.conn.execute(
                "SELECT 1 FROM card_instances WHERE user_id = ? AND user_card_id = ? AND date = ?",
                (user_id, card["id"], date),
            )
            if cur.fetchone():
                continue
            self.conn.execute(
                """
                INSERT INTO card_instances(id,user_card_id,user_id,date,status,completion_pct,notes,completed_at,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    f"ci_{uuid.uuid4().hex[:16]}",
                    card["id"],
                    user_id,
                    date,
                    "pending",
                    0,
                    None,
                    None,
                    now_iso(),
                    now_iso(),
                ),
            )
            created += 1
        self.conn.commit()
        return created

    def list_card_instances(self, user_id: str, date: str) -> list[dict[str, Any]]:
        cur = self.conn.execute(
            """
            SELECT ci.*
            FROM card_instances ci
            JOIN user_cards uc ON uc.id = ci.user_card_id
            WHERE ci.user_id = ? AND ci.date = ? AND uc.deleted_at IS NULL
            ORDER BY ci.created_at DESC
            """,
            (user_id, date),
        )
        return [dict(r) for r in cur.fetchall()]

    def complete_card_instance(self, user_id: str, instance_id: str, notes: str | None = None) -> dict[str, Any]:
        cur = self.conn.execute(
            "SELECT * FROM card_instances WHERE id = ? AND user_id = ?",
            (instance_id, user_id),
        )
        row = cur.fetchone()
        if not row:
            raise KeyError("instance_not_found")
        self.conn.execute(
            """
            UPDATE card_instances
            SET status = 'done', completion_pct = 100, notes = ?, completed_at = ?, updated_at = ?
            WHERE id = ? AND user_id = ?
            """,
            (notes, now_iso(), now_iso(), instance_id, user_id),
        )
        self.conn.commit()
        cur2 = self.conn.execute("SELECT * FROM card_instances WHERE id = ? AND user_id = ?", (instance_id, user_id))
        return dict(cur2.fetchone())

    def list_routine_steps(self, user_id: str, user_card_id: str) -> list[dict[str, Any]]:
        self.get_user_card(user_id, user_card_id)
        cur = self.conn.execute(
            """
            SELECT *
            FROM routine_steps
            WHERE user_card_id = ?
            ORDER BY position ASC, created_at ASC
            """,
            (user_card_id,),
        )
        steps: list[dict[str, Any]] = []
        for r in cur.fetchall():
            row = dict(r)
            row["is_required"] = bool(row["is_required"])
            steps.append(row)
        return steps

    def get_routine_step(self, user_id: str, step_id: str) -> dict[str, Any]:
        cur = self.conn.execute(
            """
            SELECT rs.*
            FROM routine_steps rs
            JOIN user_cards uc ON uc.id = rs.user_card_id
            WHERE rs.id = ? AND uc.user_id = ? AND uc.deleted_at IS NULL
            """,
            (step_id, user_id),
        )
        row = cur.fetchone()
        if not row:
            raise KeyError("routine_step_not_found")
        step = dict(row)
        step["is_required"] = bool(step["is_required"])
        return step

    def add_routine_step(
        self,
        user_id: str,
        user_card_id: str,
        title: str,
        is_required: bool = True,
        estimated_min: int | None = None,
        position: int | None = None,
    ) -> dict[str, Any]:
        self.get_user_card(user_id, user_card_id)
        clean_title = str(title).strip()
        if not clean_title:
            raise ValueError("title is required")
        if position is None:
            cur = self.conn.execute(
                "SELECT COALESCE(MAX(position), 0) AS mx FROM routine_steps WHERE user_card_id = ?",
                (user_card_id,),
            )
            position = int(cur.fetchone()["mx"]) + 1
        if int(position) < 1:
            raise ValueError("position must be >= 1")
        step_id = f"rs_{uuid.uuid4().hex[:16]}"
        ts = now_iso()
        self.conn.execute(
            """
            INSERT INTO routine_steps(id,user_card_id,position,title,is_required,estimated_min,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?)
            """,
            (step_id, user_card_id, int(position), clean_title, 1 if is_required else 0, estimated_min, ts, ts),
        )
        self.conn.commit()
        return self.get_routine_step(user_id, step_id)

    def update_routine_step(self, user_id: str, step_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        step = self.get_routine_step(user_id, step_id)
        title = patch.get("title", step["title"])
        if not str(title).strip():
            raise ValueError("title cannot be empty")
        position = int(patch.get("position", step["position"]))
        if position < 1:
            raise ValueError("position must be >= 1")
        is_required = 1 if patch.get("is_required", step["is_required"]) else 0
        estimated_min = patch.get("estimated_min", step.get("estimated_min"))
        self.conn.execute(
            """
            UPDATE routine_steps
            SET title = ?, is_required = ?, estimated_min = ?, position = ?, updated_at = ?
            WHERE id = ?
            """,
            (str(title).strip(), is_required, estimated_min, position, now_iso(), step_id),
        )
        self.conn.commit()
        return self.get_routine_step(user_id, step_id)

    def delete_routine_step(self, user_id: str, step_id: str) -> None:
        step = self.get_routine_step(user_id, step_id)
        self.conn.execute("DELETE FROM routine_steps WHERE id = ?", (step["id"],))
        self.conn.commit()

    def list_daily_plan_items(self, user_id: str, date: str) -> list[dict[str, Any]]:
        cur = self.conn.execute(
            """
            SELECT *
            FROM daily_plan_items
            WHERE user_id = ? AND date = ?
            ORDER BY COALESCE(start_time, ''), created_at ASC
            """,
            (user_id, date),
        )
        return [dict(r) for r in cur.fetchall()]

    def create_daily_plan_item(self, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        item_id = f"dpi_{uuid.uuid4().hex[:16]}"
        ts = now_iso()
        row = {
            "id": item_id,
            "user_id": user_id,
            "date": payload["date"],
            "user_card_id": payload["user_card_id"],
            "start_time": payload.get("start_time"),
            "end_time": payload.get("end_time"),
            "priority": int(payload.get("priority", 2)),
            "energy_level": int(payload.get("energy_level", 2)),
            "calendar_event_id": payload.get("calendar_event_id"),
            "created_at": ts,
            "updated_at": ts,
        }
        self.conn.execute(
            """
            INSERT INTO daily_plan_items(
              id,user_id,date,user_card_id,start_time,end_time,priority,energy_level,calendar_event_id,created_at,updated_at
            ) VALUES (
              :id,:user_id,:date,:user_card_id,:start_time,:end_time,:priority,:energy_level,:calendar_event_id,:created_at,:updated_at
            )
            """,
            row,
        )
        self.conn.commit()
        cur = self.conn.execute("SELECT * FROM daily_plan_items WHERE id = ? AND user_id = ?", (item_id, user_id))
        return dict(cur.fetchone())

    def list_study_subjects(self, user_id: str) -> list[dict[str, Any]]:
        cur = self.conn.execute(
            "SELECT * FROM study_subjects WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        )
        return [dict(r) for r in cur.fetchall()]

    def create_study_subject(self, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        name = str(payload.get("name", "")).strip()
        if not name:
            raise ValueError("name_required")
        subject_id = f"sub_{uuid.uuid4().hex[:16]}"
        ts = now_iso()
        row = {
            "id": subject_id,
            "user_id": user_id,
            "name": name,
            "color": payload.get("color"),
            "target_hours_week": float(payload.get("target_hours_week", 0)),
            "created_at": ts,
            "updated_at": ts,
        }
        self.conn.execute(
            """
            INSERT INTO study_subjects(id,user_id,name,color,target_hours_week,created_at,updated_at)
            VALUES(:id,:user_id,:name,:color,:target_hours_week,:created_at,:updated_at)
            """,
            row,
        )
        self.conn.commit()
        cur = self.conn.execute("SELECT * FROM study_subjects WHERE id = ? AND user_id = ?", (subject_id, user_id))
        return dict(cur.fetchone())

    @staticmethod
    def _normalize_card(row: dict[str, Any]) -> dict[str, Any]:
        row["config"] = json.loads(row.pop("config_json") or "{}")
        row["is_active"] = bool(row["is_active"])
        row["is_archived"] = bool(row["is_archived"])
        return row
