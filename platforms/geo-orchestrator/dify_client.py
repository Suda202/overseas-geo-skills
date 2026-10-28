"""Dify workflow client.

One responsibility: POST a case to the workflow run API and return the raw
body. No retry logic, no orchestration — the workflow already retries
internally.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Optional

import httpx


class DifyError(Exception):
    def __init__(self, message: str, status: Optional[int] = None, body: Any = None):
        super().__init__(message)
        self.status = status
        self.body = body


@dataclass
class DifyConfig:
    base_url: str = "http://dify.ads.qihoo.net/v1"
    api_key: str = ""
    timeout: float = 300.0

    @classmethod
    def from_env(cls) -> "DifyConfig":
        return cls(
            base_url=os.environ.get("DIFY_BASE_URL", "http://dify.ads.qihoo.net/v1").rstrip("/"),
            api_key=os.environ.get("DIFY_API_KEY", "").strip(),
            timeout=float(os.environ.get("DIFY_TIMEOUT", "300")),
        )


class DifyClient:
    def __init__(self, config: DifyConfig):
        self.config = config

    def _headers(self) -> dict:
        if not self.config.api_key:
            raise DifyError("DIFY_API_KEY is not set")
        return {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

    def run_workflow(self, inputs: dict, user: str = "orchestrator") -> dict:
        """Run the workflow and return a body shaped like Dify's blocking reply.

        Uses `response_mode: streaming` on purpose. A 17-node run takes minutes
        and the nginx in front of Dify kills idle blocking requests at 504; an
        SSE stream stays alive because Dify keeps sending events. The returned
        dict is assembled from the `workflow_finished` event so callers do not
        need to know which mode was used.
        """
        url = f"{self.config.base_url}/workflows/run"
        payload = {
            "inputs": inputs,
            "response_mode": "streaming",
            "user": user,
        }
        headers = dict(self._headers())
        headers["Accept"] = "text/event-stream"

        finished: Optional[dict] = None
        nodes: list = []
        try:
            with httpx.Client(timeout=httpx.Timeout(self.config.timeout, connect=15.0)) as client:
                with client.stream("POST", url, headers=headers, json=payload) as resp:
                    if resp.status_code != 200:
                        raw = resp.read().decode("utf-8", "replace")[:2000]
                        try:
                            body = json.loads(raw)
                        except ValueError:
                            body = {"raw": raw}
                        msg = body.get("message") or body.get("error") or raw[:500]
                        raise DifyError(
                            f"Dify HTTP {resp.status_code}: {msg}",
                            status=resp.status_code,
                            body=body,
                        )
                    for line in resp.iter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        chunk = line[5:].strip()
                        if not chunk or chunk == "[DONE]":
                            continue
                        try:
                            ev = json.loads(chunk)
                        except ValueError:
                            continue
                        kind = ev.get("event")
                        if kind == "node_finished":
                            nodes.append({
                                "node_id": ev.get("data", {}).get("node_id"),
                                "title": ev.get("data", {}).get("title"),
                                "status": ev.get("data", {}).get("status"),
                                "elapsed_time": ev.get("data", {}).get("elapsed_time"),
                            })
                        elif kind == "workflow_finished":
                            finished = ev
                        elif kind == "error":
                            raise DifyError(
                                f"Dify stream error: {ev.get('message') or ev}",
                                body=ev,
                            )
        except httpx.TimeoutException as e:
            raise DifyError(f"Dify stream timed out after {self.config.timeout}s: {e}") from e
        except httpx.RequestError as e:
            raise DifyError(f"Cannot reach Dify at {url}: {e}") from e

        if finished is None:
            raise DifyError(
                "Dify stream ended without a workflow_finished event",
                body={"nodes_seen": nodes},
            )

        data = finished.get("data") or {}
        return {
            "workflow_run_id": data.get("id"),
            "task_id": data.get("task_id"),
            "data": {
                "id": data.get("id"),
                "workflow_id": data.get("workflow_id"),
                "status": data.get("status"),
                "outputs": data.get("outputs") or {},
                "error": data.get("error"),
                "elapsed_time": data.get("elapsed_time"),
                "total_tokens": data.get("total_tokens"),
                "created_at": data.get("created_at"),
                "finished_at": data.get("finished_at"),
                "node_trace": nodes,
            },
        }

    def check_auth(self) -> dict:
        """Cheap call proving the key is accepted. Tries /info; falls back to
        a malformed run request and accepts 400 as 'authenticated'."""
        if not self.config.api_key:
            return {"auth_ok": False, "reason": "DIFY_API_KEY is not set"}
        base = self.config.base_url
        try:
            with httpx.Client(timeout=10) as client:
                r = client.get(f"{base}/info", headers=self._headers())
                if r.status_code in (200, 404):
                    # 404 means the app doesn't expose /info but auth passed.
                    return {"auth_ok": True, "via": "/info"}
                if r.status_code == 401:
                    return {"auth_ok": False, "reason": "401 unauthorized"}
                return {"auth_ok": True, "via": f"/info status {r.status_code}"}
        except DifyError as e:
            return {"auth_ok": False, "reason": str(e)}
        except httpx.RequestError as e:
            return {"auth_ok": False, "reason": f"unreachable: {e}"}
