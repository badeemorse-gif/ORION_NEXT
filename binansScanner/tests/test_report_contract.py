"""Canonical ReportResult contract tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from models.report import ReportResult
from reports.html_report import HtmlReportRenderer
from reports.json_report import JsonReportRenderer
from reports.report_exporter import ReportExporter, ReportFormat


class TestReportResultContract(unittest.TestCase):
    def test_report_result_accepts_canonical_upstream_results(self) -> None:
        report = ReportResult(symbol="BTCUSDT", summary=("canonical report",))
        self.assertEqual(report.symbol, "BTCUSDT")
        self.assertEqual(report.summary, ("canonical report",))

    def test_report_result_default_state_is_safe(self) -> None:
        report = ReportResult(symbol="BTCUSDT")
        self.assertEqual(report.symbol, "BTCUSDT")
        self.assertEqual(report.summary, ())
        self.assertEqual(report.warnings, ())

    def test_report_result_does_not_require_market_dataset(self) -> None:
        report = ReportResult(symbol="BTCUSDT")
        self.assertIsNotNone(report)

    def test_report_result_is_incomplete_when_an_upstream_result_is_missing(self) -> None:
        report = ReportResult(symbol="BTCUSDT")
        self.assertFalse(report.is_structurally_complete)

    def test_report_result_is_structurally_complete_when_all_results_exist(self) -> None:
        report = ReportResult(
            symbol="BTCUSDT",
            analysis=object(),
            execution=object(),
            profile=object(),
            scoring=object(),
        )
        self.assertTrue(report.is_structurally_complete)

    def test_report_result_metadata_is_canonical(self) -> None:
        report = ReportResult(symbol="BTCUSDT", summary=("canonical report",))
        self.assertEqual(report.metadata.symbol, "BTCUSDT")

    def test_report_result_uses_immutable_top_level_contract(self) -> None:
        report = ReportResult(symbol="BTCUSDT")
        with self.assertRaises((AttributeError, TypeError)):
            report.symbol = "ETHUSDT"  # type: ignore[misc]

    def test_report_result_warning_state(self) -> None:
        report = ReportResult(symbol="BTCUSDT", warnings=("test warning",))
        self.assertEqual(report.warnings, ("test warning",))

    def test_json_renderer_consumes_canonical_report_result(self) -> None:
        report = ReportResult(
            symbol="BTCUSDT",
            summary=("canonical report",),
            warnings=("test warning",),
        )
        rendered = JsonReportRenderer().render(report)
        payload = json.loads(rendered)
        self.assertEqual(payload["symbol"], "BTCUSDT")
        self.assertEqual(payload["summary"], ["canonical report"])
        self.assertIn("analysis", payload)
        self.assertIn("execution", payload)

    def test_html_renderer_consumes_canonical_report_result(self) -> None:
        report = ReportResult(
            symbol="BTCUSDT",
            summary=("canonical report",),
            warnings=("test warning",),
        )
        rendered = HtmlReportRenderer().render(report)
        self.assertIn("ORION Report", rendered)
        self.assertIn("BTCUSDT", rendered)
        self.assertIn("canonical report", rendered)
        self.assertIn("test warning", rendered)

    def test_report_exporter_uses_renderer_boundary(self) -> None:
        report = ReportResult(symbol="BTCUSDT")
        exporter = ReportExporter(
            html_renderer=HtmlReportRenderer(),
            json_renderer=JsonReportRenderer(),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "report.json"
            exporter.export(report, output_path, ReportFormat.JSON)
            self.assertTrue(output_path.exists())
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["symbol"], "BTCUSDT")


if __name__ == "__main__":
    unittest.main()
