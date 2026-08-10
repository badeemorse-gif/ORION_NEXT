"""Transport-level contract tests for the canonical FastAPI ApiServer."""

from __future__ import annotations

import asyncio
import json
import unittest

from fastapi.responses import JSONResponse
from starlette.requests import Request

from api.api_server import ApiServer


class _Response:
    def __init__(self, payload=None, success=True, message="ok"):
        self.payload = payload or {}
        self.success = success
        self.message = message


class _RouterDouble:
    def __init__(self):
        self.calls = []

    def health(self):
        self.calls.append("health")
        return _Response({"status": "healthy"})

    def scheduler_state(self):
        self.calls.append("scheduler_state")
        return _Response({"running": False})

    def registered_jobs(self):
        self.calls.append("registered_jobs")
        return _Response({"jobs": []})

    def run_symbol(self, request):
        self.calls.append(("run_symbol", request.endpoint, request.payload))
        return _Response({"summary": {}})

    def export_report(self, request):
        self.calls.append(("export_report", request.endpoint, request.payload))
        return _Response({"format": "json"})


def _request(body: dict) -> Request:
    encoded = json.dumps(body).encode("utf-8")
    sent = False

    async def receive():
        nonlocal sent
        if sent:
            return {"type": "http.disconnect"}
        sent = True
        return {"type": "http.request", "body": encoded, "more_body": False}

    return Request(
        {"type": "http", "method": "POST", "path": "/pipeline/run", "headers": [(b"content-type", b"application/json")]},
        receive,
    )


class TestApiServerContract(unittest.TestCase):
    def setUp(self):
        self.router = _RouterDouble()
        self.server = ApiServer(router=self.router)

    def _route(self, path: str, method: str):
        for route in self.server.app.routes:
            if getattr(route, "path", None) == path and method in getattr(route, "methods", set()):
                return route
        self.fail(f"Missing {method} route: {path}")

    def test_canonical_http_routes_are_registered(self):
        expected = {
            ("/health", "GET"),
            ("/scheduler/state", "GET"),
            ("/scheduler/jobs", "GET"),
            ("/pipeline/run", "POST"),
            ("/report/export", "POST"),
        }
        actual = {
            (route.path, method)
            for route in self.server.app.routes
            for method in getattr(route, "methods", set())
            if route.path in {path for path, _ in expected}
        }
        self.assertEqual(actual, expected)

    def test_health_endpoint_preserves_canonical_response_envelope(self):
        response = asyncio.run(self._route("/health", "GET").endpoint())
        self.assertIsInstance(response, JSONResponse)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.body), {"status": "healthy", "success": True, "message": "ok"})
        self.assertEqual(self.router.calls, ["health"])

    def test_pipeline_run_builds_canonical_request_and_delegates(self):
        response = asyncio.run(self._route("/pipeline/run", "POST").endpoint(
            _request({"request_id": "r1", "payload": {"symbol": "BTCUSDT"}})
        ))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.router.calls, [("run_symbol", "/pipeline/run", {"symbol": "BTCUSDT"})])

    def test_report_export_builds_canonical_request_and_delegates(self):
        response = asyncio.run(self._route("/report/export", "POST").endpoint(
            _request({"request_id": "r2", "endpoint": "/report/export", "payload": {"format": "json"}})
        ))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.router.calls, [("export_report", "/report/export", {"format": "json"})])

    def test_unsuccessful_pipeline_response_maps_to_unprocessable_entity(self):
        self.router.run_symbol = lambda request: _Response({"error": "invalid"}, success=False, message="invalid request")
        response = asyncio.run(self._route("/pipeline/run", "POST").endpoint(_request({"payload": {}})))
        self.assertEqual(response.status_code, 422)
        self.assertFalse(json.loads(response.body)["success"])


if __name__ == "__main__":
    unittest.main()
