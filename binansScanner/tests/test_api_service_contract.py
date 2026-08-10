import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from api.api_models import ApiRequest
from api.api_service import ApiService, ApiServiceError
from models.report import ReportResult
from reports.report_exporter import ReportFormat


class _FakeScheduler:
    def state(self):
        return type("State", (), {"running": False, "jobs_count": 0, "last_tick": None})()

    def registered_jobs(self):
        return ()


class _FakeExporter:
    def __init__(self):
        self.calls = []

    def export(self, report, output_path, report_format):
        self.calls.append((report, output_path, report_format))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("exported", encoding="utf-8")
        return output_path


class _FakePipeline:
    def __init__(self, result=None):
        self.calls = []
        self.result = result or SimpleNamespace(
            success=True,
            symbol="BTCUSDT",
            failed_stage=None,
            error_message=None,
            elapsed_ms=12.5,
            execution_result=SimpleNamespace(status=SimpleNamespace(value="EXECUTED")),
            report_result=ReportResult(symbol="BTCUSDT"),
        )

    def run_symbol(self, symbol, timeframes, quantity=None):
        self.calls.append((symbol, timeframes, quantity))
        return self.result


class TestApiServiceContract(unittest.TestCase):
    def test_health_returns_canonical_response(self):
        response = ApiService(
            scheduler=_FakeScheduler(), report_exporter=_FakeExporter()
        ).health()
        self.assertTrue(response.success)
        self.assertEqual(response.message, "OK")
        self.assertEqual(response.payload, {})

    def test_run_symbol_delegates_to_canonical_pipeline(self):
        pipeline = _FakePipeline()
        service = ApiService(
            scheduler=_FakeScheduler(),
            report_exporter=_FakeExporter(),
            pipeline=pipeline,
        )

        response = service.run_symbol(
            ApiRequest(
                request_id="req-run-1",
                endpoint="/pipeline/run",
                payload={
                    "symbol": "BTCUSDT",
                    "timeframes": ["1h", "4h"],
                    "quantity": 1.5,
                },
            )
        )

        self.assertTrue(response.success)
        self.assertEqual(pipeline.calls, [("BTCUSDT", ["1h", "4h"], 1.5)])
        self.assertEqual(response.payload["request_id"], "req-run-1")
        self.assertEqual(response.payload["execution_status"], "EXECUTED")
        self.assertTrue(response.payload["report_available"])

    def test_run_symbol_rejects_missing_pipeline(self):
        service = ApiService(
            scheduler=_FakeScheduler(), report_exporter=_FakeExporter()
        )
        with self.assertRaises(ApiServiceError):
            service.run_symbol(
                ApiRequest(
                    request_id="req-run-2",
                    endpoint="/pipeline/run",
                    payload={"symbol": "BTCUSDT", "timeframes": ["1h"]},
                )
            )

    def test_export_report_delegates_canonical_result_to_exporter(self):
        exporter = _FakeExporter()
        report = ReportResult(symbol="BTCUSDT")
        service = ApiService(scheduler=_FakeScheduler(), report_exporter=exporter)

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "report.json"
            response = service.export_report(
                ApiRequest(
                    request_id="req-1",
                    endpoint="export_report",
                    payload={
                        "report": report,
                        "output_path": target,
                        "format": "json",
                    },
                )
            )

            self.assertTrue(response.success)
            self.assertEqual(response.payload["format"], "json")
            self.assertEqual(response.payload["output_path"], str(target))
            self.assertEqual(exporter.calls, [(report, target, ReportFormat.JSON)])

    def test_export_report_rejects_missing_canonical_report(self):
        service = ApiService(
            scheduler=_FakeScheduler(), report_exporter=_FakeExporter()
        )
        with self.assertRaises(ApiServiceError):
            service.export_report(
                ApiRequest(
                    request_id="req-2",
                    endpoint="export_report",
                    payload={"output_path": "report.json", "format": "json"},
                )
            )

    def test_export_report_rejects_unsupported_format(self):
        service = ApiService(
            scheduler=_FakeScheduler(), report_exporter=_FakeExporter()
        )
        with self.assertRaises(ApiServiceError):
            service.export_report(
                ApiRequest(
                    request_id="req-3",
                    endpoint="export_report",
                    payload={
                        "report": ReportResult(symbol="BTCUSDT"),
                        "output_path": "report.txt",
                        "format": "txt",
                    },
                )
            )


if __name__ == "__main__":
    unittest.main()
