"""Auditability tests for the canonical reporting boundary."""

from __future__ import annotations

import json
import unittest

from engines.report_engine import ReportEngine
from models.analysis import AnalysisResult
from models.decision import DecisionResult
from models.execution import ExecutionResult, ExecutionStatus
from models.profile import MarketCharacteristics, ProfileResult, ProfileStatistics
from models.score import ScoreResult


class TestReportAuditability(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = ReportEngine(project_version="test")

    @staticmethod
    def _complete_inputs() -> tuple[AnalysisResult, ProfileResult, ScoreResult, DecisionResult]:
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
                reasons=["decision evidence"],
                warnings=["decision warning"],
            ),
        )

    def test_decision_evidence_is_carried_without_generation(self) -> None:
        analysis, profile, score, decision = self._complete_inputs()
        report = self.engine.build_report(
            symbol="BTCUSDT",
            analysis=analysis,
            profile=profile,
            score=score,
            decision=decision,
            execution=ExecutionResult(status=ExecutionStatus.SKIPPED, message="hold"),
            stage_trace=("ORCHESTRATION", "EXECUTION", "REPORT"),
        )

        self.assertEqual(report.audit.decision_reasons, ("decision evidence",))
        self.assertEqual(report.audit.decision_warnings, ("decision warning",))
        self.assertEqual(report.audit.stage_trace, ("ORCHESTRATION", "EXECUTION", "REPORT"))
        self.assertEqual(report.audit.execution_status, ExecutionStatus.SKIPPED)
        self.assertFalse(report.execution_failed)

    def test_execution_failure_is_explicit_and_serialized(self) -> None:
        analysis, profile, score, decision = self._complete_inputs()
        execution = ExecutionResult(
            status=ExecutionStatus.FAILED,
            message="exchange unavailable",
        )
        report = self.engine.build_report(
            symbol="BTCUSDT",
            analysis=analysis,
            profile=profile,
            score=score,
            decision=decision,
            execution=execution,
            stage_trace=("ORCHESTRATION", "EXECUTION", "REPORT"),
            failure_stage="EXECUTION",
            failure_message="exchange unavailable",
        )

        self.assertTrue(report.is_complete)
        self.assertTrue(report.execution_failed)
        self.assertEqual(report.audit.status.value, "FAILED")
        self.assertEqual(report.audit.failure_stage, "EXECUTION")
        self.assertEqual(report.audit.execution_message, "exchange unavailable")
        self.assertIn("exchange unavailable", report.warnings)

        payload = json.loads(self.engine.export_json(report))
        self.assertEqual(payload["audit"]["status"], "FAILED")
        self.assertEqual(payload["audit"]["execution_status"], "FAILED")
        self.assertEqual(payload["audit"]["failure_stage"], "EXECUTION")

    def test_missing_execution_is_incomplete_not_success(self) -> None:
        analysis, profile, score, decision = self._complete_inputs()
        report = self.engine.build_report(
            symbol="BTCUSDT",
            analysis=analysis,
            profile=profile,
            score=score,
            decision=decision,
            execution=None,
        )

        self.assertFalse(report.is_complete)
        self.assertEqual(report.audit.status.value, "INCOMPLETE")
        self.assertIsNone(report.audit.execution_status)


if __name__ == "__main__":
    unittest.main()
