from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from repository import Repo


@dataclass
class SyncResult:
    processed: int
    pushed: int
    failed: int


class SyncWorker:
    def __init__(
        self,
        repo: Repo,
        remote_base_url: str,
        device_id: str,
        timeout_seconds: float = 8.0,
        max_retry: int = 5,
    ) -> None:
        self.repo = repo
        self.remote_base_url = remote_base_url.rstrip("/")
        self.device_id = device_id
        self.timeout_seconds = timeout_seconds
        self.max_retry = max_retry

    def push_pending(self, user_id: str, limit: int = 50) -> SyncResult:
        pending = self.repo.list_pending_sync_changes(user_id=user_id, limit=limit, max_retry=self.max_retry)
        if not pending:
            return SyncResult(processed=0, pushed=0, failed=0)

        for item in pending:
            self.repo.mark_sync_change_status(item["id"], "processing")

        payload = {
            "device_id": self.device_id,
            "changes": [
                {
                    "change_id": row["id"],
                    "entity": row["entity"],
                    "entity_id": row["entity_id"],
                    "operation": row["operation"],
                    "version": row["version"],
                    "payload": json.loads(row["payload_json"] or "{}"),
                    "updated_at": row["updated_at"],
                }
                for row in pending
            ],
        }

        req = urllib.request.Request(
            f"{self.remote_base_url}/v1/sync/push",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {user_id}"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as res:
                body = json.loads(res.read().decode("utf-8") or "{}")
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            err = f"push_error:{type(exc).__name__}"
            for row in pending:
                self.repo.mark_sync_change_status(row["id"], "failed", error=err, bump_retry=True)
            return SyncResult(processed=len(pending), pushed=0, failed=len(pending))

        data = body.get("data", {}) if isinstance(body, dict) else {}
        accepted = set(data.get("accepted", []))
        rejected = {str(r.get("change_id")): str(r.get("reason", "rejected")) for r in data.get("rejected", []) if isinstance(r, dict)}

        pushed = 0
        failed = 0
        for row in pending:
            change_id = row["id"]
            if change_id in accepted:
                self.repo.mark_sync_change_status(change_id, "done", error=None, bump_retry=False)
                pushed += 1
                continue
            reason = rejected.get(change_id, "not_accepted")
            self.repo.mark_sync_change_status(change_id, "failed", error=reason, bump_retry=True)
            failed += 1

        return SyncResult(processed=len(pending), pushed=pushed, failed=failed)

    @staticmethod
    def next_backoff_seconds(retry_count: int, base_seconds: int = 5, max_seconds: int = 300) -> int:
        retry = max(0, retry_count)
        return min(max_seconds, base_seconds * (2 ** retry))


if __name__ == "__main__":
    repo = Repo("backend/app.db")
    repo.init_schema()
    worker = SyncWorker(repo=repo, remote_base_url="http://127.0.0.1:8787", device_id="local_worker")

    while True:
        result = worker.push_pending(user_id="usr_demo", limit=50)
        print(json.dumps(result.__dict__))
        time.sleep(10)
