"""Canonical ReportResult and report-rendering contract tests."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from models.analysis import AnalysisResult
from models.decision import DecisionResult
from models.execution import ExecutionResult
from models.profile import (
    MarketCharacteristics,
    ProfileResult,
    ProfileStatistics,
)
from models.report import ReportMetadata, ReportResult
from models.score import ScoreResult
from reports.html_report import HtmlReportRenderer
from reports.json_report import JsonReportRenderer
from reports.report_exporter import ReportFormat, ReportExporter


class TestReportResultContract(unittest.TestCase):
    """Verify the canonical ReportResult domain and rendering boundaries."""

    def _build_profile_result(self) -> ProfileResult:
        return ProfileResult(
            symbol="BTCUSDT",
            market=MarketCharacteristics(),
            statistics=ProfileStatistics(),
        )

    def _build_complete_report(self) -> ReportResult:
        return ReportResult(
            symbol="BTCUSDT",
            analysis=AnalysisResult(),
            profile=self._build_profile_result(),
            score=ScoreResult(),
            decision=DecisionResult(),
            execution=ExecutionResult(),
        )

    def test_report_result_accepts_canonical_upstream_results(self) -> None:
        analysis = AnalysisResult()
        profile = self._build_profile_result()
        score = ScoreResult()
        decision = DecisionResult()
        execution = ExecutionResult()

        report = ReportResult(
            symbol="BTCUSDT",
            analysis=analysis,
            profile=profile,
            score=score,
            decision=decision,
            execution=execution,
        )

        self.assertIs(report.analysis, analysis)
        self.assertIs(report.profile, profile)
        self.assertIs(report.score, score)
        self.assertIs(report.decision, decision)
        self.assertIs(report.execution, execution)

    def test_report_result_is_structurally_complete_when_all_results_exist(self) -> None:
        report = self._build_complete_report()
        self.assertTrue(report.is_complete)

    def test_report_result_is_incomplete_when_an_upstream_result_is_missing(self) -> None:
        report = self._build_complete_report()
        incomplete_report = ReportResult(
            symbol=report.symbol,
            analysis=report.analysis,
            profile=report.profile,
            score=report.score,
            decision=report.decision,
            execution=None,
        )
        self.assertFalse(incomplete_report.is_complete)

    def test_report_result_warning_state(self) -> None:
        report = ReportResult(symbol="BTCUSDT", warnings=("execution skipped",))
        self.assertTrue(report.has_warnings)

    def test_report_result_metadata_is_canonical(self) -> None:
        metadata = ReportMetadata(
            project_version="2.0.0",
            report_name="ORION Report",
            execution_time_ms=12.5,
        )
        report = ReportResult(symbol="BTCUSDT", metadata=metadata)
        self.assertIs(report.metadata, metadata)
        self.assertEqual(report.metadata.project_version, "2.0.0")
        self.assertEqual(report.metadata.report_name, "ORION Report")
        self.assertEqual(report.metadata.execution_time_ms, 12.5)

    def test_report_result_does_not_require_market_dataset(self) -> None:
        report = ReportResult(symbol="BTCUSDT")
        self.assertEqual(report.symbol, "BTCUSDT")
        self.assertFalse(report.is_complete)

    def test_report_result_uses_immutable_top_level_contract(self) -> None:
        report = ReportResult(symbol="BTCUSDT")
        with self.assertRaises(AttributeError):
            report.symbol = "ETHUSDT"

    def test_report_result_default_state_is_safe(self) -> None:
        report = ReportResult(symbol="BTCUSDT")
        self.assertEqual(report.summary, ())
        self.assertEqual(report.highlights, ())
        self.assertEqual(report.warnings, ())
        self.assertIsInstance(report.metadata, ReportMetadata)
        self.assertFalse(report.has_warnings)
        self.assertFalse(report.is_complete)

    def test_json_renderer_consumes_canonical_report_result(self) -> None:
        report = self._build_complete_report()
        report = ReportResult(
            symbol=report.symbol,
            analysis=report.analysis,
            profile=report.profile,
            score=report.score,
            decision=report.decision,
            execution=report.execution,
            summary=("canonical report",),
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
        exporter = ReportExporter()
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "report.json"
            exporter.export(report, output_path, ReportFormat.JSON)
            self.assertTrue(output_path.exists())
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["symbol"], "BTCUSDT")


if __name__ == "__main__":
    unittest.main()
