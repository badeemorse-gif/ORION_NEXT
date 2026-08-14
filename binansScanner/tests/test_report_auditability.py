"""Auditability tests for the canonical Execution -> Report boundary."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from engines.report_engine import ReportEngine
from models.analysis import AnalysisResult
from models.decision import DecisionResult
from models.execution import ExecutionResult, ExecutionStatus
from models.profile import MarketCharacteristics, ProfileResult, ProfileStatistics
from models.score import ScoreResult
from reports.html_report import HtmlReportRenderer
from reports.json_report import JsonReportRenderer
from reports.report_exporter import ReportExporter, ReportFormat


class TestReportAuditability(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = ReportEngine(project_version="test")

    @staticmethod
    def _complete_inputs() -> tuple[AnalysisResult, ProfileResult, ScoreResult, DecisionResult]:
        return (
            AnalysisResult(),
            ProfileResult(symbol="BTCUSDT", market=MarketCharacteristics(), statistics=ProfileStatistics()),
            ScoreResult(),
            DecisionResult(decision="WAIT", reasons=["decision evidence"], warnings=["decision warning"]),
        )

    def test_successful_execution_is_complete(self) -> None:
        analysis, profile, score, decision = self._complete_inputs()
        report = self.engine.build_report(
            symbol="BTCUSDT", analysis=analysis, profile=profile, score=score, decision=decision,
            execution=ExecutionResult(status=ExecutionStatus.EXECUTED, message="executed", order_id="PAPER-1"),
            stage_trace=("ORCHESTRATION", "EXECUTION", "REPORT"),
        )
        self.assertEqual(report.audit.status.value, "COMPLETE")
        self.assertTrue(report.is_successful)
        self.assertEqual(report.audit.execution_status, ExecutionStatus.EXECUTED)
        self.assertEqual(report.audit.order_id, "PAPER-1")

    def test_skipped_execution_is_complete(self) -> None:
        analysis, profile, score, decision = self._complete_inputs()
        report = self.engine.build_report(
            symbol="BTCUSDT", analysis=analysis, profile=profile, score=score, decision=decision,
            execution=ExecutionResult(status=ExecutionStatus.SKIPPED, message="hold"),
            stage_trace=("ORCHESTRATION", "EXECUTION", "REPORT"),
        )
        self.assertEqual(report.audit.status.value, "COMPLETE")
        self.assertEqual(report.audit.execution_status, ExecutionStatus.SKIPPED)
        self.assertFalse(report.execution_failed)

    def test_execution_failure_is_failed_evidence(self) -> None:
        analysis, profile, score, decision = self._complete_inputs()
        execution = ExecutionResult(status=ExecutionStatus.FAILED, message="exchange unavailable")
        report = self.engine.build_report(
            symbol="BTCUSDT", analysis=analysis, profile=profile, score=score, decision=decision,
            execution=execution,
            stage_trace=("ORCHESTRATION", "EXECUTION", "REPORT"),
            failure_stage="EXECUTION",
        )
        self.assertEqual(report.audit.status.value, "FAILED")
        self.assertFalse(report.is_successful)
        self.assertTrue(report.execution_failed)
        self.assertEqual(report.audit.execution_status, ExecutionStatus.FAILED)
        self.assertEqual(report.audit.failure_stage, "EXECUTION")
        self.assertEqual(report.audit.failure_message, "exchange unavailable")
        self.assertEqual(report.audit.stage_trace, ("ORCHESTRATION", "EXECUTION", "REPORT"))

    def test_orchestration_failure_evidence(self) -> None:
        report = self.engine.build_report(
            symbol="BTCUSDT", analysis=None, profile=None, score=None, decision=None, execution=None,
            stage_trace=("ORCHESTRATION", "REPORT"),
            failure_stage="ORCHESTRATION",
            failure_message="provider validation failed",
        )
        self.assertEqual(report.audit.status.value, "FAILED")
        self.assertIsNone(report.audit.execution_status)
        self.assertEqual(report.audit.failure_stage, "ORCHESTRATION")
        self.assertEqual(report.audit.failure_message, "provider validation failed")
        self.assertFalse(report.is_successful)

    def test_incomplete_report_is_distinct_from_failure(self) -> None:
        analysis, profile, score, decision = self._complete_inputs()
        report = self.engine.build_report(
            symbol="BTCUSDT", analysis=analysis, profile=profile, score=score, decision=decision, execution=None,
        )
        self.assertEqual(report.audit.status.value, "INCOMPLETE")
        self.assertFalse(report.is_successful)
        self.assertIsNone(report.audit.failure_stage)

    def test_failed_state_survives_engine_json_and_renderers(self) -> None:
        analysis, profile, score, decision = self._complete_inputs()
        report = self.engine.build_report(
            symbol="BTCUSDT", analysis=analysis, profile=profile, score=score, decision=decision,
            execution=ExecutionResult(status=ExecutionStatus.FAILED, message="forced failure"),
            stage_trace=("ORCHESTRATION", "EXECUTION", "REPORT"),
            failure_stage="EXECUTION",
        )
        payload = json.loads(self.engine.export_json(report))
        self.assertEqual(payload["audit"]["status"], "FAILED")
        self.assertEqual(payload["audit"]["execution_status"], "FAILED")
        self.assertEqual(payload["audit"]["failure_stage"], "EXECUTION")

        json_payload = json.loads(JsonReportRenderer().render(report))
        self.assertEqual(json_payload["audit"]["status"], "FAILED")
        html = HtmlReportRenderer().render(report)
        self.assertIn("FAILED", html)
        self.assertIn("EXECUTION", html)
        self.assertIn("forced failure", html)

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "failed.json"
            ReportExporter(HtmlReportRenderer(), JsonReportRenderer()).export(report, path, ReportFormat.JSON)
            exported = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(exported["audit"]["status"], "FAILED")


if __name__ == "__main__":
    unittest.main()
