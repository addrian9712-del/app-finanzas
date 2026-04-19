import json
import socket
import threading
import time
import unittest
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from repository import Repo
from sync_worker import SyncWorker


class _PushHandler(BaseHTTPRequestHandler):
    mode = "success"

    def do_POST(self):
        if self.path != "/v1/sync/push":
            self.send_response(404)
            self.end_headers()
            return

        if self.mode == "error":
            self.send_response(500)
            self.end_headers()
            return

        size = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(size).decode("utf-8") or "{}")
        accepted = [ch["change_id"] for ch in payload.get("changes", [])]
        body = json.dumps({"data": {"accepted": accepted, "rejected": []}}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        return


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class SyncWorkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.port = _free_port()
        cls.server = ThreadingHTTPServer(("127.0.0.1", cls.port), _PushHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=1)

    def setUp(self):
        self.repo = Repo(":memory:")
        self.repo.init_schema()
        self.user = "usr_worker"
        self.repo.push_sync_changes(
            self.user,
            [
                {
                    "change_id": "chg_sync_1",
                    "entity": "user_card",
                    "entity_id": "uc_1",
                    "operation": "update",
                    "version": 1,
                    "payload": {"title": "Demo"},
                }
            ],
        )
        self.worker = SyncWorker(
            repo=self.repo,
            remote_base_url=f"http://127.0.0.1:{self.port}",
            device_id="dev_test",
        )

    def test_push_pending_success_marks_done(self):
        _PushHandler.mode = "success"
        result = self.worker.push_pending(self.user)
        self.assertEqual(result.processed, 1)
        self.assertEqual(result.pushed, 1)
        self.assertEqual(result.failed, 0)
        self.assertEqual(result.skipped, 0)
        self.assertEqual(result.dead, 0)

        row = self.repo.conn.execute("SELECT status, retry_count FROM sync_queue WHERE id = 'chg_sync_1'").fetchone()
        self.assertEqual(row["status"], "done")
        self.assertEqual(row["retry_count"], 0)

    def test_push_pending_error_marks_failed_and_retry_increment(self):
        _PushHandler.mode = "error"
        result = self.worker.push_pending(self.user)
        self.assertEqual(result.processed, 1)
        self.assertEqual(result.pushed, 0)
        self.assertEqual(result.failed, 1)
        self.assertEqual(result.skipped, 0)
        self.assertEqual(result.dead, 0)

        row = self.repo.conn.execute("SELECT status, retry_count FROM sync_queue WHERE id = 'chg_sync_1'").fetchone()
        self.assertEqual(row["status"], "failed")
        self.assertEqual(row["retry_count"], 1)

    def test_backoff_grows_exponentially_with_cap(self):
        self.assertEqual(SyncWorker.next_backoff_seconds(0), 5)
        self.assertEqual(SyncWorker.next_backoff_seconds(1), 10)
        self.assertEqual(SyncWorker.next_backoff_seconds(2), 20)
        self.assertEqual(SyncWorker.next_backoff_seconds(10), 300)

    def test_failed_change_is_skipped_until_backoff_expires(self):
        self.repo.conn.execute(
            "UPDATE sync_queue SET status='failed', retry_count=1, updated_at=? WHERE id='chg_sync_1'",
            (datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),),
        )
        self.repo.conn.commit()
        _PushHandler.mode = "success"
        result = self.worker.push_pending(self.user)
        self.assertEqual(result.processed, 0)
        self.assertEqual(result.skipped, 1)

    def test_dead_letter_after_max_retry(self):
        self.repo.conn.execute(
            "UPDATE sync_queue SET status='failed', retry_count=5, updated_at=? WHERE id='chg_sync_1'",
            ((datetime.now(timezone.utc) - timedelta(hours=1)).isoformat().replace("+00:00", "Z"),),
        )
        self.repo.conn.commit()
        _PushHandler.mode = "success"
        result = self.worker.push_pending(self.user)
        self.assertEqual(result.dead, 1)
        row = self.repo.conn.execute("SELECT status FROM sync_queue WHERE id='chg_sync_1'").fetchone()
        self.assertEqual(row["status"], "dead")


if __name__ == "__main__":
    unittest.main()
