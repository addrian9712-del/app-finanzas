from __future__ import annotations

import json
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from repository import Repo


def with_cors(handler: BaseHTTPRequestHandler) -> None:
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, DELETE, OPTIONS")


def json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    with_cors(handler)
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def parse_body(handler: BaseHTTPRequestHandler) -> tuple[dict, str | None]:
    try:
        length = int(handler.headers.get("Content-Length", "0"))
    except ValueError:
        return {}, "invalid content-length"
    raw = handler.rfile.read(length) if length > 0 else b"{}"
    try:
        data = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        return {}, "invalid json body"
    if not isinstance(data, dict):
        return {}, "json body must be an object"
    return data, None


def auth_user(handler: BaseHTTPRequestHandler) -> str:
    auth = handler.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth.removeprefix("Bearer ").strip() or "usr_demo"
    return "usr_demo"


def is_iso_date(value: str) -> bool:
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def is_iso_datetime(value: str) -> bool:
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def build_handler(repo: Repo):
    class Handler(BaseHTTPRequestHandler):
        def do_OPTIONS(self) -> None:
            self.send_response(HTTPStatus.NO_CONTENT)
            with_cors(self)
            self.end_headers()

        def do_GET(self) -> None:
            user_id = auth_user(self)
            url = urlparse(self.path)

            if url.path == "/v1/user-cards":
                cards = repo.list_user_cards(user_id)
                return json_response(self, HTTPStatus.OK, {"data": cards})

            if url.path == "/v1/card-templates":
                qs = parse_qs(url.query)
                type_filter = qs.get("type", [None])[0]
                templates = repo.list_card_templates(type_filter)
                return json_response(self, HTTPStatus.OK, {"data": templates})

            if url.path == "/v1/card-instances":
                qs = parse_qs(url.query)
                date = qs.get("date", [None])[0]
                if not date:
                    return json_response(self, HTTPStatus.BAD_REQUEST, {"error": {"code": "VALIDATION_ERROR", "message": "date is required"}})
                if not is_iso_date(date):
                    return json_response(self, HTTPStatus.BAD_REQUEST, {"error": {"code": "VALIDATION_ERROR", "message": "date must be YYYY-MM-DD"}})
                instances = repo.list_card_instances(user_id, date)
                return json_response(self, HTTPStatus.OK, {"data": instances})

            if url.path == "/v1/daily-plan-items":
                qs = parse_qs(url.query)
                date = qs.get("date", [None])[0]
                if not date:
                    return json_response(self, HTTPStatus.BAD_REQUEST, {"error": {"code": "VALIDATION_ERROR", "message": "date is required"}})
                if not is_iso_date(date):
                    return json_response(self, HTTPStatus.BAD_REQUEST, {"error": {"code": "VALIDATION_ERROR", "message": "date must be YYYY-MM-DD"}})
                items = repo.list_daily_plan_items(user_id, date)
                return json_response(self, HTTPStatus.OK, {"data": items})

            if url.path == "/v1/study-subjects":
                subjects = repo.list_study_subjects(user_id)
                return json_response(self, HTTPStatus.OK, {"data": subjects})

            if url.path.startswith("/v1/user-cards/") and url.path.endswith("/routine-steps"):
                user_card_id = url.path.split("/")[-2]
                try:
                    steps = repo.list_routine_steps(user_id, user_card_id)
                except KeyError:
                    return json_response(self, HTTPStatus.NOT_FOUND, {"error": {"code": "NOT_FOUND"}})
                return json_response(self, HTTPStatus.OK, {"data": steps})

            if url.path.startswith("/v1/user-cards/"):
                card_id = url.path.split("/")[-1]
                try:
                    card = repo.get_user_card(user_id, card_id)
                except KeyError:
                    return json_response(self, HTTPStatus.NOT_FOUND, {"error": {"code": "NOT_FOUND"}})
                return json_response(self, HTTPStatus.OK, {"data": card})

            if url.path == "/v1/sync/pull":
                qs = parse_qs(url.query)
                since = qs.get("since", [None])[0]
                device_id = qs.get("device_id", [None])[0]
                if not device_id:
                    return json_response(self, HTTPStatus.BAD_REQUEST, {"error": {"code": "VALIDATION_ERROR", "message": "device_id is required"}})
                if not since:
                    return json_response(self, HTTPStatus.BAD_REQUEST, {"error": {"code": "VALIDATION_ERROR", "message": "since is required"}})
                if not is_iso_datetime(since):
                    return json_response(self, HTTPStatus.BAD_REQUEST, {"error": {"code": "VALIDATION_ERROR", "message": "since must be ISO date-time"}})
                changes = repo.pull_sync_changes(user_id, since)
                return json_response(self, HTTPStatus.OK, {"data": {"changes": changes}})

            return json_response(self, HTTPStatus.NOT_FOUND, {"error": {"code": "NOT_FOUND"}})

        def do_POST(self) -> None:
            user_id = auth_user(self)
            url = urlparse(self.path)
            payload, err = parse_body(self)
            if err:
                return json_response(self, HTTPStatus.BAD_REQUEST, {"error": {"code": "VALIDATION_ERROR", "message": err}})

            if url.path == "/v1/user-cards":
                required = {"type", "title"}
                if not required.issubset(payload):
                    return json_response(self, HTTPStatus.BAD_REQUEST, {"error": {"code": "VALIDATION_ERROR", "message": "type and title are required"}})
                try:
                    card = repo.create_user_card(user_id, payload)
                except ValueError as e:
                    return json_response(self, HTTPStatus.BAD_REQUEST, {"error": {"code": "VALIDATION_ERROR", "message": str(e)}})
                return json_response(self, HTTPStatus.CREATED, {"data": card})

            if url.path == "/v1/sync/push":
                device_id = str(payload.get("device_id", "")).strip()
                changes = payload.get("changes", [])
                if not device_id:
                    return json_response(self, HTTPStatus.BAD_REQUEST, {"error": {"code": "VALIDATION_ERROR", "message": "device_id is required"}})
                if not isinstance(changes, list):
                    return json_response(self, HTTPStatus.BAD_REQUEST, {"error": {"code": "VALIDATION_ERROR", "message": "changes must be a list"}})
                result = repo.push_sync_changes(user_id, changes)
                return json_response(self, HTTPStatus.OK, {"data": result})

            if url.path == "/v1/card-instances/generate":
                date = payload.get("date")
                if not date:
                    return json_response(self, HTTPStatus.BAD_REQUEST, {"error": {"code": "VALIDATION_ERROR", "message": "date is required"}})
                if not is_iso_date(str(date)):
                    return json_response(self, HTTPStatus.BAD_REQUEST, {"error": {"code": "VALIDATION_ERROR", "message": "date must be YYYY-MM-DD"}})
                created = repo.generate_daily_instances(user_id, date)
                return json_response(self, HTTPStatus.OK, {"data": {"created": created, "date": date}})

            if url.path == "/v1/daily-plan-items":
                date = str(payload.get("date", ""))
                user_card_id = str(payload.get("user_card_id", "")).strip()
                if not is_iso_date(date):
                    return json_response(self, HTTPStatus.BAD_REQUEST, {"error": {"code": "VALIDATION_ERROR", "message": "date must be YYYY-MM-DD"}})
                if not user_card_id:
                    return json_response(self, HTTPStatus.BAD_REQUEST, {"error": {"code": "VALIDATION_ERROR", "message": "user_card_id is required"}})
                item = repo.create_daily_plan_item(user_id, payload)
                return json_response(self, HTTPStatus.CREATED, {"data": item})

            if url.path == "/v1/study-subjects":
                try:
                    subject = repo.create_study_subject(user_id, payload)
                except ValueError as e:
                    return json_response(self, HTTPStatus.BAD_REQUEST, {"error": {"code": "VALIDATION_ERROR", "message": str(e)}})
                return json_response(self, HTTPStatus.CREATED, {"data": subject})

            if url.path.startswith("/v1/user-cards/") and url.path.endswith("/routine-steps"):
                user_card_id = url.path.split("/")[-2]
                title = payload.get("title")
                if not str(title or "").strip():
                    return json_response(self, HTTPStatus.BAD_REQUEST, {"error": {"code": "VALIDATION_ERROR", "message": "title is required"}})
                try:
                    step = repo.add_routine_step(
                        user_id=user_id,
                        user_card_id=user_card_id,
                        title=str(title),
                        is_required=bool(payload.get("is_required", True)),
                        estimated_min=payload.get("estimated_min"),
                        position=payload.get("position"),
                    )
                except KeyError:
                    return json_response(self, HTTPStatus.NOT_FOUND, {"error": {"code": "NOT_FOUND"}})
                except ValueError as e:
                    return json_response(self, HTTPStatus.BAD_REQUEST, {"error": {"code": "VALIDATION_ERROR", "message": str(e)}})
                return json_response(self, HTTPStatus.CREATED, {"data": step})

            if url.path.startswith("/v1/card-instances/") and url.path.endswith("/complete"):
                instance_id = url.path.split("/")[-2]
                notes = payload.get("notes")
                try:
                    updated = repo.complete_card_instance(user_id, instance_id, notes)
                except KeyError:
                    return json_response(self, HTTPStatus.NOT_FOUND, {"error": {"code": "NOT_FOUND"}})
                return json_response(self, HTTPStatus.OK, {"data": updated})

            return json_response(self, HTTPStatus.NOT_FOUND, {"error": {"code": "NOT_FOUND"}})

        def do_PATCH(self) -> None:
            user_id = auth_user(self)
            url = urlparse(self.path)
            payload, err = parse_body(self)
            if err:
                return json_response(self, HTTPStatus.BAD_REQUEST, {"error": {"code": "VALIDATION_ERROR", "message": err}})

            if url.path.startswith("/v1/user-cards/"):
                card_id = url.path.split("/")[-1]
                try:
                    card = repo.update_user_card(user_id, card_id, payload)
                except KeyError:
                    return json_response(self, HTTPStatus.NOT_FOUND, {"error": {"code": "NOT_FOUND"}})
                except ValueError as e:
                    return json_response(self, HTTPStatus.BAD_REQUEST, {"error": {"code": "VALIDATION_ERROR", "message": str(e)}})
                return json_response(self, HTTPStatus.OK, {"data": card})

            if url.path.startswith("/v1/routine-steps/"):
                step_id = url.path.split("/")[-1]
                try:
                    step = repo.update_routine_step(user_id, step_id, payload)
                except KeyError:
                    return json_response(self, HTTPStatus.NOT_FOUND, {"error": {"code": "NOT_FOUND"}})
                except ValueError as e:
                    return json_response(self, HTTPStatus.BAD_REQUEST, {"error": {"code": "VALIDATION_ERROR", "message": str(e)}})
                return json_response(self, HTTPStatus.OK, {"data": step})

            return json_response(self, HTTPStatus.NOT_FOUND, {"error": {"code": "NOT_FOUND"}})

        def do_DELETE(self) -> None:
            user_id = auth_user(self)
            url = urlparse(self.path)

            if url.path.startswith("/v1/user-cards/"):
                card_id = url.path.split("/")[-1]
                try:
                    repo.delete_user_card(user_id, card_id)
                except KeyError:
                    return json_response(self, HTTPStatus.NOT_FOUND, {"error": {"code": "NOT_FOUND"}})
                self.send_response(HTTPStatus.NO_CONTENT)
                with_cors(self)
                self.end_headers()
                return

            if url.path.startswith("/v1/routine-steps/"):
                step_id = url.path.split("/")[-1]
                try:
                    repo.delete_routine_step(user_id, step_id)
                except KeyError:
                    return json_response(self, HTTPStatus.NOT_FOUND, {"error": {"code": "NOT_FOUND"}})
                self.send_response(HTTPStatus.NO_CONTENT)
                with_cors(self)
                self.end_headers()
                return

            return json_response(self, HTTPStatus.NOT_FOUND, {"error": {"code": "NOT_FOUND"}})

        def log_message(self, format: str, *args) -> None:
            return

    return Handler


def create_app_server(host: str = "0.0.0.0", port: int = 8787, db_path: str = "backend/app.db") -> ThreadingHTTPServer:
    repo = Repo(db_path)
    repo.init_schema()
    return ThreadingHTTPServer((host, port), build_handler(repo))


if __name__ == "__main__":
    server = create_app_server()
    print("Mock API running at http://0.0.0.0:8787")
    server.serve_forever()
