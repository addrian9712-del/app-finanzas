from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from repository import Repo


repo = Repo("backend/app.db")
repo.init_schema()


def json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def parse_body(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0"))
    raw = handler.rfile.read(length) if length > 0 else b"{}"
    return json.loads(raw.decode("utf-8"))


def auth_user(handler: BaseHTTPRequestHandler) -> str:
    # Mock auth: Bearer <user_id>
    auth = handler.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth.removeprefix("Bearer ").strip() or "usr_demo"
    return "usr_demo"


class Handler(BaseHTTPRequestHandler):
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
            instances = repo.list_card_instances(user_id, date)
            return json_response(self, HTTPStatus.OK, {"data": instances})

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
            changes = repo.pull_sync_changes(user_id, since)
            return json_response(self, HTTPStatus.OK, {"data": {"changes": changes}})

        return json_response(self, HTTPStatus.NOT_FOUND, {"error": {"code": "NOT_FOUND"}})

    def do_POST(self) -> None:
        user_id = auth_user(self)
        url = urlparse(self.path)
        payload = parse_body(self)

        if url.path == "/v1/user-cards":
            required = {"type", "title"}
            if not required.issubset(payload):
                return json_response(self, HTTPStatus.BAD_REQUEST, {"error": {"code": "VALIDATION_ERROR"}})
            card = repo.create_user_card(user_id, payload)
            return json_response(self, HTTPStatus.CREATED, {"data": card})

        if url.path == "/v1/sync/push":
            changes = payload.get("changes", [])
            if not isinstance(changes, list):
                return json_response(self, HTTPStatus.BAD_REQUEST, {"error": {"code": "VALIDATION_ERROR"}})
            result = repo.push_sync_changes(user_id, changes)
            return json_response(self, HTTPStatus.OK, {"data": result})

        if url.path == "/v1/card-instances/generate":
            date = payload.get("date")
            if not date:
                return json_response(self, HTTPStatus.BAD_REQUEST, {"error": {"code": "VALIDATION_ERROR", "message": "date is required"}})
            created = repo.generate_daily_instances(user_id, date)
            return json_response(self, HTTPStatus.OK, {"data": {"created": created, "date": date}})

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

        if url.path.startswith("/v1/user-cards/"):
            card_id = url.path.split("/")[-1]
            payload = parse_body(self)
            try:
                card = repo.update_user_card(user_id, card_id, payload)
            except KeyError:
                return json_response(self, HTTPStatus.NOT_FOUND, {"error": {"code": "NOT_FOUND"}})
            except ValueError as e:
                return json_response(self, HTTPStatus.BAD_REQUEST, {"error": {"code": "VALIDATION_ERROR", "message": str(e)}})
            return json_response(self, HTTPStatus.OK, {"data": card})

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
            self.end_headers()
            return

        return json_response(self, HTTPStatus.NOT_FOUND, {"error": {"code": "NOT_FOUND"}})

    def log_message(self, format: str, *args) -> None:
        return


if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", 8787), Handler)
    print("Mock API running at http://0.0.0.0:8787")
    server.serve_forever()
