import json
import socket
import threading
import time
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from mock_server import create_app_server


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class MockServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.port = free_port()
        cls.server = create_app_server(host="127.0.0.1", port=cls.port, db_path=":memory:")
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.15)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=1)

    def url(self, path: str) -> str:
        return f"http://127.0.0.1:{self.port}{path}"

    def request_json(self, method: str, path: str, data: dict | None = None, expected_status: int = 200):
        payload = None if data is None else json.dumps(data).encode("utf-8")
        req = Request(self.url(path), data=payload, method=method)
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", "Bearer usr_test")
        try:
            with urlopen(req) as res:
                body = res.read().decode("utf-8")
                self.assertEqual(res.status, expected_status)
                if body:
                    return json.loads(body)
                return None
        except HTTPError as e:
            body = e.read().decode("utf-8")
            if e.code != expected_status:
                raise
            return json.loads(body) if body else None

    def test_templates_and_card_flow(self):
        templates = self.request_json("GET", "/v1/card-templates")
        self.assertGreaterEqual(len(templates["data"]), 1)

        created = self.request_json(
            "POST",
            "/v1/user-cards",
            {"type": "routine", "title": "Hydration", "config": {"frequency": {"kind": "daily"}}},
            expected_status=201,
        )
        card_id = created["data"]["id"]

        fetched = self.request_json("GET", f"/v1/user-cards/{card_id}")
        self.assertEqual(fetched["data"]["title"], "Hydration")

    def test_instances_and_completion(self):
        self.request_json(
            "POST",
            "/v1/user-cards",
            {"type": "task", "title": "Plan day", "config": {"frequency": {"kind": "daily"}}},
            expected_status=201,
        )
        gen = self.request_json("POST", "/v1/card-instances/generate", {"date": "2026-04-20"})
        self.assertGreaterEqual(gen["data"]["created"], 1)

        items = self.request_json("GET", "/v1/card-instances?date=2026-04-20")
        self.assertGreaterEqual(len(items["data"]), 1)

        instance_id = items["data"][0]["id"]
        done = self.request_json("POST", f"/v1/card-instances/{instance_id}/complete", {"notes": "done"})
        self.assertEqual(done["data"]["status"], "done")

    def test_invalid_domain_values(self):
        bad_type = self.request_json(
            "POST",
            "/v1/user-cards",
            {"type": "unknown", "title": "invalid"},
            expected_status=400,
        )
        self.assertEqual(bad_type["error"]["code"], "VALIDATION_ERROR")

        bad_date = self.request_json("POST", "/v1/card-instances/generate", {"date": "20-04-2026"}, expected_status=400)
        self.assertEqual(bad_date["error"]["code"], "VALIDATION_ERROR")

    def test_invalid_json_returns_validation_error(self):
        req = Request(self.url("/v1/user-cards"), data=b"{bad-json", method="POST")
        req.add_header("Content-Type", "application/json")
        with self.assertRaises(HTTPError) as ctx:
            urlopen(req)
        self.assertEqual(ctx.exception.code, 400)
        payload = json.loads(ctx.exception.read().decode("utf-8"))
        self.assertEqual(payload["error"]["code"], "VALIDATION_ERROR")

    def test_routine_steps_flow(self):
        created = self.request_json(
            "POST",
            "/v1/user-cards",
            {"type": "routine", "title": "Rutina agua", "config": {"frequency": {"kind": "daily"}}},
            expected_status=201,
        )
        card_id = created["data"]["id"]

        step = self.request_json(
            "POST",
            f"/v1/user-cards/{card_id}/routine-steps",
            {"title": "Tomar agua", "position": 1},
            expected_status=201,
        )
        step_id = step["data"]["id"]

        listed = self.request_json("GET", f"/v1/user-cards/{card_id}/routine-steps")
        self.assertEqual(len(listed["data"]), 1)
        self.assertEqual(listed["data"][0]["id"], step_id)

        patched = self.request_json("PATCH", f"/v1/routine-steps/{step_id}", {"title": "Tomar 2 vasos"})
        self.assertEqual(patched["data"]["title"], "Tomar 2 vasos")

        self.request_json("DELETE", f"/v1/routine-steps/{step_id}", expected_status=204)
        listed_after = self.request_json("GET", f"/v1/user-cards/{card_id}/routine-steps")
        self.assertEqual(len(listed_after["data"]), 0)

    def test_sync_conflict_cases_and_required_device_id(self):
        missing_device = self.request_json("POST", "/v1/sync/push", {"changes": []}, expected_status=400)
        self.assertEqual(missing_device["error"]["code"], "VALIDATION_ERROR")

        first = self.request_json(
            "POST",
            "/v1/sync/push",
            {
                "device_id": "dev_1",
                "changes": [
                    {
                        "change_id": "chg_dup_http",
                        "entity": "user_card",
                        "entity_id": "uc_1",
                        "operation": "update",
                        "version": 1,
                        "payload": {"title": "A"},
                    }
                ],
            },
        )
        second = self.request_json(
            "POST",
            "/v1/sync/push",
            {
                "device_id": "dev_1",
                "changes": [
                    {
                        "change_id": "chg_dup_http",
                        "entity": "user_card",
                        "entity_id": "uc_1",
                        "operation": "update",
                        "version": 1,
                        "payload": {"title": "A"},
                    }
                ],
            },
        )
        self.assertEqual(first["data"]["accepted"], ["chg_dup_http"])
        self.assertEqual(second["data"]["accepted"], ["chg_dup_http"])
        self.assertEqual(second["data"]["rejected"], [])

        missing_pull_device = self.request_json("GET", "/v1/sync/pull?since=2026-04-20T00:00:00Z", expected_status=400)
        self.assertEqual(missing_pull_device["error"]["code"], "VALIDATION_ERROR")
        missing_pull_since = self.request_json("GET", "/v1/sync/pull?device_id=dev_1", expected_status=400)
        self.assertEqual(missing_pull_since["error"]["code"], "VALIDATION_ERROR")

    def test_daily_plan_and_study_subjects_are_implemented(self):
        card = self.request_json(
            "POST",
            "/v1/user-cards",
            {"type": "task", "title": "Plan day", "config": {"frequency": {"kind": "daily"}}},
            expected_status=201,
        )
        card_id = card["data"]["id"]
        created_plan = self.request_json(
            "POST",
            "/v1/daily-plan-items",
            {"date": "2026-04-20", "user_card_id": card_id, "priority": 1},
            expected_status=201,
        )
        self.assertEqual(created_plan["data"]["user_card_id"], card_id)

        listed_plan = self.request_json("GET", "/v1/daily-plan-items?date=2026-04-20")
        self.assertGreaterEqual(len(listed_plan["data"]), 1)

        created_subject = self.request_json("POST", "/v1/study-subjects", {"name": "Matemáticas"}, expected_status=201)
        self.assertEqual(created_subject["data"]["name"], "Matemáticas")
        listed_subjects = self.request_json("GET", "/v1/study-subjects")
        self.assertGreaterEqual(len(listed_subjects["data"]), 1)


if __name__ == "__main__":
    unittest.main()
