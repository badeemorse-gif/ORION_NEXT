"""
===============================================================================
ORION
Module : tests.test_report_contract
Version: 1.0.0

Canonical ReportResult contract tests.

These tests verify that ReportResult:
    - aggregates canonical upstream result contracts;
    - remains independent from MarketDataset;
    - exposes structural completeness correctly;
    - does not require report renderer/exporter state.
===============================================================================
"""

from __future__ import annotations

import unittest

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


class TestReportResultContract(unittest.TestCase):
    """Verify the canonical ReportResult domain contract."""

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
        """ReportResult must aggregate the canonical result contracts."""

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

    def test_report_result_is_structurally_complete_when_all_results_exist(
        self,
    ) -> None:
        """All canonical upstream results must make the report structurally complete."""

        report = self._build_complete_report()

        self.assertTrue(report.is_complete)

    def test_report_result_is_incomplete_when_an_upstream_result_is_missing(
        self,
    ) -> None:
        """Missing any canonical upstream result must make the report incomplete."""

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
        """Warnings must be exposed through the canonical warning boundary."""

        report = ReportResult(
            symbol="BTCUSDT",
            warnings=("execution skipped",),
        )

        self.assertTrue(report.has_warnings)

    def test_report_result_metadata_is_canonical(self) -> None:
        """Metadata must be represented by ReportMetadata, not an export dictionary."""

        metadata = ReportMetadata(
            project_version="2.0.0",
            report_name="ORION Report",
            execution_time_ms=12.5,
        )

        report = ReportResult(
            symbol="BTCUSDT",
            metadata=metadata,
        )

        self.assertIs(report.metadata, metadata)
        self.assertEqual(report.metadata.project_version, "2.0.0")
        self.assertEqual(report.metadata.report_name, "ORION Report")
        self.assertEqual(report.metadata.execution_time_ms, 12.5)

    def test_report_result_does_not_require_market_dataset(self) -> None:
        """
        ReportResult construction must not require MarketDataset.

        This protects the Result Contract boundary against the legacy
        dataset-as-container architecture.
        """

        report = ReportResult(symbol="BTCUSDT")

        self.assertEqual(report.symbol, "BTCUSDT")
        self.assertFalse(report.is_complete)

    def test_report_result_uses_immutable_top_level_contract(self) -> None:
        """Canonical report state must be immutable at the dataclass level."""

        report = ReportResult(symbol="BTCUSDT")

        with self.assertRaises(AttributeError):
            report.symbol = "ETHUSDT"

    def test_report_result_default_state_is_safe(self) -> None:
        """Default collections and metadata must be initialized safely."""

        report = ReportResult(symbol="BTCUSDT")

        self.assertEqual(report.summary, ())
        self.assertEqual(report.highlights, ())
        self.assertEqual(report.warnings, ())
        self.assertIsInstance(report.metadata, ReportMetadata)
        self.assertFalse(report.has_warnings)
        self.assertFalse(report.is_complete)


if __name__ == "__main__":
    unittest.main()