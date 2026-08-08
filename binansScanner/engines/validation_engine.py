"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : engines.validation_engine
Version      : 1.3.0
Status       : ORION Production V1.0 APPROVED BUILD
===============================================================================

Rule-based Validation Engine adhering to OCP and DIP via abstract Validatable
protocols for verifying structural and semantic integrity across all dataset
components without direct type coupling.
===============================================================================
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional, Protocol, runtime_checkable

from models.market import MarketDataset, TimeframeData

base_logger = logging.getLogger(__name__)


# =============================================================================
# Configuration, Enums & Codes
# =============================================================================

@dataclass(frozen=True)
class ValidationConfig:
    ENGINE_VERSION: str = "1.3.0"
    STRICT_MODE: bool = True
    MIN_SCORE_BOUND: float = 0.0
    MAX_SCORE_BOUND: float = 100.0


class ValidationStatus(str, Enum):
    PASSED = "PASSED"
    WARNING = "WARNING"
    FAILED = "FAILED"


@dataclass(frozen=True)
class ValidationCodes:
    # Metadata
    META_DATASET_NONE: str = "META_001"
    META_INVALID_SYMBOL: str = "META_002"
    META_MISSING_EXCHANGE: str = "META_003"
    META_MISSING_SOURCE: str = "META_004"
    META_MISSING_DOWNLOADED_AT: str = "META_005"

    # Timeframes
    TF_MISSING_DICT: str = "TF_001"
    TF_EMPTY_COLLECTION: str = "TF_002"
    TF_DUPLICATE: str = "TF_003"
    TF_INVALID_TYPE: str = "TF_004"
    TF_EMPTY_DATAFRAME: str = "TF_005"
    TF_INVALID_CANDLES_COUNT: str = "TF_006"

    # Profile
    PROF_MISSING: str = "PROF_001"
    PROF_INVALID: str = "PROF_002"

    # Score
    SCORE_MISSING: str = "SCORE_001"
    SCORE_OUT_OF_BOUNDS: str = "SCORE_002"

    # Decision
    DEC_MISSING: str = "DEC_001"
    DEC_INVALID: str = "DEC_002"
    DEC_MISSING_RISK: str = "DEC_003"
    DEC_INVALID_POS_FACTOR: str = "DEC_004"
    DEC_EMPTY_REASONS: str = "DEC_005"

    # Report
    REP_MISSING: str = "REP_001"
    REP_EMPTY_SUMMARY: str = "REP_002"
    REP_MISSING_METADATA: str = "REP_003"
    REP_MISSING_JSON_READY: str = "REP_004"


# =============================================================================
# Validatable Protocol (Dependency Inversion Principle - DIP)
# =============================================================================

@runtime_checkable
class Validatable(Protocol):
    """
    Protocol defining a standard validation interface for any domain model,
    decoupling ValidationEngine from concrete classes.
    """

    def validate(self) -> bool:
        """Execute component-specific internal validation and return True if valid."""
        ...


# =============================================================================
# Custom Exceptions
# =============================================================================

class ValidationEngineError(Exception):
    """Base exception for all validation engine related errors."""
    pass


class DatasetValidationError(ValidationEngineError):
    """Raised when dataset semantic or structural validation fails completely."""
    pass


# =============================================================================
# Result Dataclasses
# =============================================================================

@dataclass(slots=True)
class ValidationIssue:
    """
    Immutable representation of an individual check issue or warning.
    """
    code: str = ""
    message: str = ""
    status: ValidationStatus = ValidationStatus.WARNING
    module: str = ""


@dataclass(slots=True)
class ValidationReport:
    """
    Immutable structured report holding validation findings, metrics, and summary.
    """
    total_checks: int = 0
    total_errors: int = 0
    total_warnings: int = 0
    passed: bool = True
    duration: float = 0.0
    issues: list[ValidationIssue] = field(default_factory=list)
    summary: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ValidationResult:
    """
    Immutable dataclass holding aggregated validation status, findings, and metadata.
    """
    status: ValidationStatus = ValidationStatus.PASSED
    passed: bool = True
    warnings: list[ValidationIssue] = field(default_factory=list)
    errors: list[ValidationIssue] = field(default_factory=list)
    elapsed_ms: float = 0.0
    validated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    checks: int = 0
    report: ValidationReport = field(default_factory=ValidationReport)


# =============================================================================
# Logger Adapter
# =============================================================================

class LoggerAdapter(logging.LoggerAdapter):
    """
    Custom LoggerAdapter to inject contextual validation metrics into every log record.
    """

    def process(self, msg: str, kwargs: Any) -> tuple[str, dict[str, Any]]:
        context = self.extra or {}
        context_str = " | ".join(f"{k}={v}" for k, v in context.items() if v is not None)
        if context_str:
            formatted_msg = f"[{context_str}] {msg}"
        else:
            formatted_msg = msg
        return formatted_msg, kwargs


# =============================================================================
# Abstract Base Rule & Concrete Rule Implementations (OCP & DIP)
# =============================================================================

class ValidationRule(ABC):
    """
    Abstract base class for validation rules, enabling open/closed extensions.
    """

    @abstractmethod
    def validate(self, dataset: MarketDataset, config: ValidationConfig) -> tuple[list[ValidationIssue], list[ValidationIssue], int]:
        """
        Execute rule validation against dataset.
        Returns a tuple of (errors, warnings, checks_count).
        """
        pass


class MetadataRule(ValidationRule):
    def validate(self, dataset: MarketDataset, config: ValidationConfig) -> tuple[list[ValidationIssue], list[ValidationIssue], int]:
        errors: list[ValidationIssue] = []
        warnings: list[ValidationIssue] = []
        checks = 0

        if dataset is None:
            errors.append(ValidationIssue(code=ValidationCodes.META_DATASET_NONE, message="Dataset is None", status=ValidationStatus.FAILED, module="metadata"))
            return errors, warnings, 1

        checks += 1
        if not dataset.symbol or not isinstance(dataset.symbol, str):
            errors.append(ValidationIssue(code=ValidationCodes.META_INVALID_SYMBOL, message="Missing or invalid dataset symbol", status=ValidationStatus.FAILED, module="metadata"))

        checks += 1
        exchange = getattr(dataset, "exchange", None)
        if not exchange:
            warnings.append(ValidationIssue(code=ValidationCodes.META_MISSING_EXCHANGE, message="Missing exchange metadata", status=ValidationStatus.WARNING, module="metadata"))

        checks += 1
        source = getattr(dataset, "source", None)
        if not source:
            warnings.append(ValidationIssue(code=ValidationCodes.META_MISSING_SOURCE, message="Missing source identifier metadata", status=ValidationStatus.WARNING, module="metadata"))

        checks += 1
        downloaded_at = getattr(dataset, "downloaded_at", None)
        if downloaded_at is None:
            warnings.append(ValidationIssue(code=ValidationCodes.META_MISSING_DOWNLOADED_AT, message="Missing downloaded_at timestamp", status=ValidationStatus.WARNING, module="metadata"))

        return errors, warnings, checks


class TimeframeRule(ValidationRule):
    def validate(self, dataset: MarketDataset, config: ValidationConfig) -> tuple[list[ValidationIssue], list[ValidationIssue], int]:
        errors: list[ValidationIssue] = []
        warnings: list[ValidationIssue] = []
        checks = 0

        checks += 1
        timeframes = getattr(dataset, "timeframes", {})
        if not timeframes or not isinstance(timeframes, dict):
            errors.append(ValidationIssue(code=ValidationCodes.TF_MISSING_DICT, message="Dataset contains no timeframes dictionary", status=ValidationStatus.FAILED, module="timeframes"))
            return errors, warnings, checks

        checks += 1
        if len(timeframes) == 0:
            errors.append(ValidationIssue(code=ValidationCodes.TF_EMPTY_COLLECTION, message="At least one timeframe is required", status=ValidationStatus.FAILED, module="timeframes"))

        seen_tfs: set[str] = set()
        for tf_key, tf_data in timeframes.items():
            checks += 1
            tf_str = tf_key.value if hasattr(tf_key, "value") else str(tf_key)
            if tf_str in seen_tfs:
                errors.append(ValidationIssue(code=ValidationCodes.TF_DUPLICATE, message=f"Duplicate timeframe detected: {tf_str}", status=ValidationStatus.FAILED, module="timeframes"))
            seen_tfs.add(tf_str)

            checks += 1
            if not isinstance(tf_data, TimeframeData):
                errors.append(ValidationIssue(code=ValidationCodes.TF_INVALID_TYPE, message=f"Invalid timeframe container type for {tf_str}", status=ValidationStatus.FAILED, module="timeframes"))
                continue

            checks += 1
            df = getattr(tf_data, "dataframe", None)
            if df is None or df.empty:
                errors.append(ValidationIssue(code=ValidationCodes.TF_EMPTY_DATAFRAME, message=f"DataFrame is empty or None for timeframe {tf_str}", status=ValidationStatus.FAILED, module="timeframes"))
            else:
                checks += 1
                if len(df) <= 0:
                    errors.append(ValidationIssue(code=ValidationCodes.TF_INVALID_CANDLES_COUNT, message=f"Candles count must be > 0 for timeframe {tf_str}", status=ValidationStatus.FAILED, module="timeframes"))

        return errors, warnings, checks


class ProfileRule(ValidationRule):
    def validate(self, dataset: MarketDataset, config: ValidationConfig) -> tuple[list[ValidationIssue], list[ValidationIssue], int]:
        errors: list[ValidationIssue] = []
        warnings: list[ValidationIssue] = []
        checks = 0

        checks += 1
        profile = getattr(dataset, "profile", None)
        if profile is None:
            errors.append(ValidationIssue(code=ValidationCodes.PROF_MISSING, message="MarketProfile is missing or None", status=ValidationStatus.FAILED, module="profile"))
            return errors, warnings, checks

        checks += 1
        if not isinstance(profile, Validatable):
            errors.append(ValidationIssue(code=ValidationCodes.PROF_INVALID, message="MarketProfile does not implement Validatable protocol", status=ValidationStatus.FAILED, module="profile"))
        else:
            try:
                is_valid = profile.validate()
                if not is_valid:
                    errors.append(ValidationIssue(code=ValidationCodes.PROF_INVALID, message="MarketProfile internal validation failed", status=ValidationStatus.FAILED, module="profile"))
            except Exception as e:
                errors.append(ValidationIssue(code=ValidationCodes.PROF_INVALID, message=f"MarketProfile validation exception: {e}", status=ValidationStatus.FAILED, module="profile"))

        return errors, warnings, checks


class ScoreRule(ValidationRule):
    def validate(self, dataset: MarketDataset, config: ValidationConfig) -> tuple[list[ValidationIssue], list[ValidationIssue], int]:
        errors: list[ValidationIssue] = []
        warnings: list[ValidationIssue] = []
        checks = 0

        checks += 1
        score = getattr(dataset, "score", None)
        if score is None:
            errors.append(ValidationIssue(code=ValidationCodes.SCORE_MISSING, message="ScoreResult is missing or None", status=ValidationStatus.FAILED, module="score"))
            return errors, warnings, checks

        checks += 1
        total_score = getattr(score, "total_score", -1.0)
        if total_score < config.MIN_SCORE_BOUND or total_score > config.MAX_SCORE_BOUND:
            errors.append(ValidationIssue(code=ValidationCodes.SCORE_OUT_OF_BOUNDS, message=f"Score out of valid bounds (0-100): {total_score}", status=ValidationStatus.FAILED, module="score"))

        return errors, warnings, checks


class DecisionRule(ValidationRule):
    def validate(self, dataset: MarketDataset, config: ValidationConfig) -> tuple[list[ValidationIssue], list[ValidationIssue], int]:
        errors: list[ValidationIssue] = []
        warnings: list[ValidationIssue] = []
        checks = 0

        checks += 1
        decision = getattr(dataset, "decision", None)
        if decision is None:
            errors.append(ValidationIssue(code=ValidationCodes.DEC_MISSING, message="DecisionResult is missing or None", status=ValidationStatus.FAILED, module="decision"))
            return errors, warnings, checks

        checks += 1
        if getattr(decision, "decision", None) is None:
            errors.append(ValidationIssue(code=ValidationCodes.DEC_INVALID, message="DecisionResult is missing decision type", status=ValidationStatus.FAILED, module="decision"))

        checks += 1
        if getattr(decision, "risk", None) is None:
            errors.append(ValidationIssue(code=ValidationCodes.DEC_MISSING_RISK, message="DecisionResult is missing risk level", status=ValidationStatus.FAILED, module="decision"))

        checks += 1
        pos_factor = getattr(decision, "position_size_factor", -1.0)
        if pos_factor < 0.0 or pos_factor > 1.0:
            errors.append(ValidationIssue(code=ValidationCodes.DEC_INVALID_POS_FACTOR, message=f"Invalid position size factor bounds (0.0-1.0): {pos_factor}", status=ValidationStatus.FAILED, module="decision"))

        checks += 1
        reason_codes = getattr(decision, "reason_codes", [])
        if not reason_codes or not isinstance(reason_codes, list) or len(reason_codes) == 0:
            warnings.append(ValidationIssue(code=ValidationCodes.DEC_EMPTY_REASONS, message="DecisionResult reason codes list is empty", status=ValidationStatus.WARNING, module="decision"))

        return errors, warnings, checks


class ReportRule(ValidationRule):
    def validate(self, dataset: MarketDataset, config: ValidationConfig) -> tuple[list[ValidationIssue], list[ValidationIssue], int]:
        errors: list[ValidationIssue] = []
        warnings: list[ValidationIssue] = []
        checks = 0

        checks += 1
        report = getattr(dataset, "report", None)
        if report is None:
            errors.append(ValidationIssue(code=ValidationCodes.REP_MISSING, message="ReportResult is missing or None", status=ValidationStatus.FAILED, module="report"))
            return errors, warnings, checks

        checks += 1
        summary = getattr(report, "summary", [])
        if not summary or len(summary) == 0:
            warnings.append(ValidationIssue(code=ValidationCodes.REP_EMPTY_SUMMARY, message="Report summary is empty", status=ValidationStatus.WARNING, module="report"))

        checks += 1
        metadata = getattr(report, "metadata", {})
        if not metadata:
            warnings.append(ValidationIssue(code=ValidationCodes.REP_MISSING_METADATA, message="Report metadata is missing or empty", status=ValidationStatus.WARNING, module="report"))

        checks += 1
        json_ready = getattr(report, "json_ready", {})
        if not json_ready:
            errors.append(ValidationIssue(code=ValidationCodes.REP_MISSING_JSON_READY, message="Report json_ready dictionary is missing or empty", status=ValidationStatus.FAILED, module="report"))

        return errors, warnings, checks


# =============================================================================
# Validation Engine
# =============================================================================

class ValidationEngine:
    """
    Stateless, rule-based validation engine adhering strictly to Open/Closed Principles (OCP)
    and Dependency Inversion Principles (DIP) via abstract Validatable protocols.
    """

    def __init__(self, rules: Optional[list[ValidationRule]] = None) -> None:
        self.logger = LoggerAdapter(
            base_logger,
            {
                "symbol": None,
                "status": None,
                "checks": 0,
                "warnings": 0,
                "errors": 0,
                "elapsed_ms": None,
                "operation": "init",
            },
        )
        self.config = ValidationConfig()
        self.rules: list[ValidationRule] = rules if rules is not None else [
            MetadataRule(),
            TimeframeRule(),
            ProfileRule(),
            ScoreRule(),
            DecisionRule(),
            ReportRule(),
        ]

    def register_rule(self, rule: ValidationRule) -> None:
        """
        Dynamically register a new validation rule to extend engine capabilities (OCP).
        """
        self.rules.append(rule)

    def validate_dataset(self, dataset: MarketDataset) -> ValidationResult:
        """
        Execute all registered validation rules against a MarketDataset immutably,
        returning a comprehensive ValidationResult without modifying the dataset directly.
        """
        symbol = dataset.symbol if dataset and dataset.symbol else "UNKNOWN"
        start_time = time.time()

        errors: list[ValidationIssue] = []
        warnings: list[ValidationIssue] = []
        total_checks = 0

        try:
            for rule in self.rules:
                rule_errs, rule_warns, rule_checks = rule.validate(dataset, self.config)
                errors.extend(rule_errs)
                warnings.extend(rule_warns)
                total_checks += rule_checks

            elapsed_ms = (time.time() - start_time) * 1000.0
            validation_result = self._finalize_result(errors, warnings, total_checks, elapsed_ms)

            self.logger.extra.update({
                "symbol": symbol,
                "status": validation_result.status.value,
                "checks": total_checks,
                "warnings": len(warnings),
                "errors": len(errors),
                "elapsed_ms": elapsed_ms,
                "operation": "validate_dataset",
            })
            self.logger.info("Dataset validation successfully completed.")

            if self.config.STRICT_MODE and errors:
                raise DatasetValidationError(f"Dataset validation failed for {symbol} with {len(errors)} error(s).")

        except Exception as e:
            if isinstance(e, DatasetValidationError):
                raise
            raise ValidationEngineError(f"Unexpected error during dataset validation for {symbol}: {e}") from e

        return validation_result

    # -------------------------------------------------------------------------
    # Internal Finalization & Summary Helpers
    # -------------------------------------------------------------------------

    def _finalize_result(
        self,
        errors: list[ValidationIssue],
        warnings: list[ValidationIssue],
        checks: int,
        elapsed_ms: float,
    ) -> ValidationResult:
        """Aggregate issues into a structured ValidationResult and ValidationReport."""
        status = ValidationStatus.PASSED
        passed = True

        if errors:
            status = ValidationStatus.FAILED
            passed = False
        elif warnings:
            status = ValidationStatus.WARNING
            passed = True

        all_issues = errors + warnings

        summary_lines = [
            f"Validation Status: {status.value}",
            f"Total Checks: {checks}",
            f"Errors Encountered: {len(errors)}",
            f"Warnings Encountered: {len(warnings)}",
            f"Execution Time: {elapsed_ms:.2f}ms",
        ]

        report = ValidationReport(
            total_checks=checks,
            total_errors=len(errors),
            total_warnings=len(warnings),
            passed=passed,
            duration=elapsed_ms,
            issues=all_issues,
            summary=summary_lines,
        )

        return ValidationResult(
            status=status,
            passed=passed,
            warnings=warnings,
            errors=errors,
            elapsed_ms=elapsed_ms,
            validated_at=datetime.now(timezone.utc),
            checks=checks,
            report=report,
        )


# =============================================================================
# End Of File
# =============================================================================