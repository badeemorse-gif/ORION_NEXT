"""Final Execution FAILED -> Failure Evidence Report contract test."""

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
from models.report import ReportAuditStatus
from models.score import ScoreResult
from reports.html_report import HtmlReportRenderer
from reports.json_report import JsonReportRenderer
from reports.report_exporter import ReportExporter, ReportFormat


class TestExecutionFailClosedBoundary(unittest.TestCase):
    @staticmethod
    def _inputs() -> tuple[AnalysisResult, ProfileResult, ScoreResult, DecisionResult]:
        return (
            AnalysisResult(),
            ProfileResult(
                symbol="BTCUSDT",
                market=MarketCharacteristics(),
                statistics=ProfileStatistics(),
            ),
            ScoreResult(),
            DecisionResult(
                decision="WAIT",
                reasons=["failure-evidence fixture"],
            ),
        )

    def test_failed_execution_failure_evidence_report_can_be_built_and_exported(self) -> None:
        analysis, profile, score, decision = self._inputs()
        execution = ExecutionResult(
            status=ExecutionStatus.FAILED,
            message="forced execution failure",
        )

        report = ReportEngine(project_version="test").build_report(
            symbol="BTCUSDT",
            analysis=analysis,
            profile=profile,
            score=score,
            decision=decision,
            execution=execution,
            stage_trace=("ORCHESTRATION", "EXECUTION", "REPORT"),
            failure_stage="EXECUTION",
            failure_message="forced execution failure",
        )

        self.assertIs(report.execution, execution)
        self.assertEqual(report.audit.status, ReportAuditStatus.FAILED)
        self.assertEqual(report.audit.execution_status, ExecutionStatus.FAILED)
        self.assertFalse(report.execution_succeeded)
        self.assertEqual(report.audit.failure_stage, "EXECUTION")
        self.assertEqual(report.audit.failure_message, "forced execution failure")
        self.assertEqual(
            report.audit.stage_trace,
            ("ORCHESTRATION", "EXECUTION", "REPORT"),
        )

        engine = ReportEngine(project_version="test")
        payload = json.loads(engine.export_json(report))
        self.assertEqual(payload["audit"]["status"], "FAILED")
        self.assertEqual(payload["audit"]["execution_status"], "FAILED")
        self.assertEqual(payload["audit"]["failure_stage"], "EXECUTION")

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "failure-evidence.json"
            ReportExporter(HtmlReportRenderer(), JsonReportRenderer()).export(
                report,
                output_path,
                ReportFormat.JSON,
            )
            exported = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(exported["audit"]["status"], "FAILED")
            self.assertEqual(exported["audit"]["execution_status"], "FAILED")

        # Report success semantics are intentionally absent: Pipeline.success
        # remains owned by PipelineItemResult and is never inferred from export.
        self.assertFalse(report.execution_succeeded)


if __name__ == "__main__":
    unittest.main()
