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

    def test_failed_execution_preserves_failure_evidence_through_export(self) -> None:
        analysis, profile, score, decision = self._inputs()
        execution = ExecutionResult(
            status=ExecutionStatus.FAILED,
            message="forced execution failure",
        )
        failure_stage = "EXECUTION"
        failure_message = "forced execution failure"
        stage_trace = ("ORCHESTRATION", "EXECUTION", "REPORT")

        report = ReportEngine(project_version="test").build_report(
            symbol="BTCUSDT",
            analysis=analysis,
            profile=profile,
            score=score,
            decision=decision,
            execution=execution,
            stage_trace=stage_trace,
            failure_stage=failure_stage,
            failure_message=failure_message,
        )

        # Execution FAILED remains FAILED and the exact ExecutionResult is retained.
        self.assertIs(report.execution, execution)
        self.assertEqual(report.execution.status, ExecutionStatus.FAILED)
        self.assertEqual(report.audit.status, ReportAuditStatus.FAILED)
        self.assertEqual(report.audit.execution_status, ExecutionStatus.FAILED)
        self.assertFalse(report.execution_succeeded)

        # All operational failure evidence survives the Report boundary unchanged.
        self.assertEqual(report.audit.failure_stage, failure_stage)
        self.assertEqual(report.audit.failure_message, failure_message)
        self.assertEqual(report.audit.stage_trace, stage_trace)

        engine = ReportEngine(project_version="test")
        payload = json.loads(engine.export_json(report))
        self.assertEqual(payload["audit"]["status"], "FAILED")
        self.assertEqual(payload["audit"]["execution_status"], "FAILED")
        self.assertEqual(payload["audit"]["failure_stage"], failure_stage)
        self.assertEqual(payload["audit"]["failure_message"], failure_message)
        self.assertEqual(payload["audit"]["stage_trace"], list(stage_trace))

        # Renderer/exporter may write Failure Evidence, but must not reinterpret it.
        json_rendered = json.loads(JsonReportRenderer().render(report))
        self.assertEqual(json_rendered["audit"]["status"], "FAILED")
        self.assertEqual(json_rendered["audit"]["execution_status"], "FAILED")

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "failure-evidence.json"
            exported_path = ReportExporter(HtmlReportRenderer(), JsonReportRenderer()).export(
                report,
                output_path,
                ReportFormat.JSON,
            )
            self.assertEqual(exported_path, output_path)
            exported = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(exported["audit"]["status"], "FAILED")
            self.assertEqual(exported["audit"]["execution_status"], "FAILED")
            self.assertEqual(exported["audit"]["failure_stage"], failure_stage)
            self.assertEqual(exported["audit"]["failure_message"], failure_message)
            self.assertEqual(exported["audit"]["stage_trace"], list(stage_trace))

        # No report/export API is allowed to imply Pipeline.success.
        self.assertFalse(report.execution_succeeded)


if __name__ == "__main__":
    unittest.main()
