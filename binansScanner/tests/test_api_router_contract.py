import unittest

from api.api_models import ApiRequest, ApiResponse
from api.api_router import ApiRouter


class _FakeApiService:
    def health(self):
        return ApiResponse(True, "OK", {})

    def scheduler_state(self):
        return ApiResponse(True, "state", {"running": False})

    def registered_jobs(self):
        return ApiResponse(True, "jobs", {"jobs": [], "count": 0})

    def run_symbol(self, request):
        return ApiResponse(True, "run", {"request_id": request.request_id})

    def export_report(self, request):
        return ApiResponse(True, "exported", {"request_id": request.request_id})


class TestApiRouterContract(unittest.TestCase):
    def setUp(self):
        self.router = ApiRouter(service=_FakeApiService())

    def test_available_routes_are_canonical(self):
        self.assertEqual(
            self.router.available_routes(),
            (
                "health",
                "scheduler_state",
                "registered_jobs",
                "run_symbol",
                "export_report",
            ),
        )

    def test_router_delegates_health(self):
        response = self.router.health()
        self.assertTrue(response.success)
        self.assertEqual(response.message, "OK")

    def test_router_delegates_run_symbol(self):
        response = self.router.run_symbol(
            ApiRequest(
                request_id="req-run-1",
                endpoint="/pipeline/run",
                payload={"symbol": "BTCUSDT", "timeframes": ["1h"]},
            )
        )
        self.assertTrue(response.success)
        self.assertEqual(response.payload["request_id"], "req-run-1")

    def test_router_delegates_export_report(self):
        response = self.router.export_report(
            ApiRequest(request_id="req-1", endpoint="/report/export")
        )
        self.assertTrue(response.success)
        self.assertEqual(response.payload["request_id"], "req-1")


if __name__ == "__main__":
    unittest.main()
