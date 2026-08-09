"""ORION market-data validation boundary.

Validation at this layer is intentionally limited to the MarketDataset contract.
Downstream Analysis/Profile/Score/Decision/Report contracts are not required to
exist during market-data validation.
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


@dataclass(frozen=True)
class ValidationConfig:
    ENGINE_VERSION: str = "1.4.0"
    STRICT_MODE: bool = True
    MIN_SCORE_BOUND: float = 0.0
    MAX_SCORE_BOUND: float = 100.0


class ValidationStatus(str, Enum):
    PASSED = "PASSED"
    WARNING = "WARNING"
    FAILED = "FAILED"


@dataclass(frozen=True)
class ValidationCodes:
    META_DATASET_NONE: str = "META_001"
    META_INVALID_SYMBOL: str = "META_002"
    META_MISSING_EXCHANGE: str = "META_003"
    META_MISSING_SOURCE: str = "META_004"
    META_MISSING_DOWNLOADED_AT: str = "META_005"
    TF_MISSING_DICT: str = "TF_001"
    TF_EMPTY_COLLECTION: str = "TF_002"
    TF_DUPLICATE: str = "TF_003"
    TF_INVALID_TYPE: str = "TF_004"
    TF_EMPTY_DATAFRAME: str = "TF_005"
    TF_INVALID_CANDLES_COUNT: str = "TF_006"
    PROF_MISSING: str = "PROF_001"
    PROF_INVALID: str = "PROF_002"
    SCORE_MISSING: str = "SCORE_001"
    SCORE_OUT_OF_BOUNDS: str = "SCORE_002"
    DEC_MISSING: str = "DEC_001"
    DEC_INVALID: str = "DEC_002"
    DEC_MISSING_RISK: str = "DEC_003"
    DEC_INVALID_POS_FACTOR: str = "DEC_004"
    DEC_EMPTY_REASONS: str = "DEC_005"
    REP_MISSING: str = "REP_001"
    REP_EMPTY_SUMMARY: str = "REP_002"
    REP_MISSING_METADATA: str = "REP_003"
    REP_MISSING_JSON_READY: str = "REP_004"


@runtime_checkable
class Validatable(Protocol):
    def validate(self) -> bool:
        ...


class ValidationEngineError(Exception):
    """Base validation failure."""


class DatasetValidationError(ValidationEngineError):
    """Raised when the MarketDataset boundary fails in strict mode."""


@dataclass(slots=True)
class ValidationIssue:
    code: str = ""
    message: str = ""
    status: ValidationStatus = ValidationStatus.WARNING
    module: str = ""


@dataclass(slots=True)
class ValidationReport:
    total_checks: int = 0
    total_errors: int = 0
    total_warnings: int = 0
    passed: bool = True
    duration: float = 0.0
    issues: list[ValidationIssue] = field(default_factory=list)
    summary: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ValidationResult:
    status: ValidationStatus = ValidationStatus.PASSED
    passed: bool = True
    warnings: list[ValidationIssue] = field(default_factory=list)
    errors: list[ValidationIssue] = field(default_factory=list)
    elapsed_ms: float = 0.0
    validated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    checks: int = 0
    report: ValidationReport = field(default_factory=ValidationReport)


class LoggerAdapter(logging.LoggerAdapter):
    def process(self, msg: str, kwargs: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        context = self.extra or {}
        text = " | ".join(f"{k}={v}" for k, v in context.items() if v is not None)
        return (f"[{text}] {msg}" if text else msg), kwargs


class ValidationRule(ABC):
    @abstractmethod
    def validate(self, dataset: MarketDataset, config: ValidationConfig) -> tuple[list[ValidationIssue], list[ValidationIssue], int]:
        ...


class MetadataRule(ValidationRule):
    def validate(self, dataset, config):
        errors, warnings, checks = [], [], 0
        if dataset is None:
            return [ValidationIssue(ValidationCodes.META_DATASET_NONE, "Dataset is None", ValidationStatus.FAILED, "metadata")], warnings, 1
        checks += 1
        if not isinstance(dataset.symbol, str) or not dataset.symbol.strip():
            errors.append(ValidationIssue(ValidationCodes.META_INVALID_SYMBOL, "Missing or invalid dataset symbol", ValidationStatus.FAILED, "metadata"))
        checks += 1
        if not getattr(dataset, "exchange", None):
            warnings.append(ValidationIssue(ValidationCodes.META_MISSING_EXCHANGE, "Missing exchange metadata", ValidationStatus.WARNING, "metadata"))
        checks += 1
        if not getattr(dataset, "source", None):
            warnings.append(ValidationIssue(ValidationCodes.META_MISSING_SOURCE, "Missing source identifier metadata", ValidationStatus.WARNING, "metadata"))
        checks += 1
        if getattr(dataset, "downloaded_at", None) is None:
            warnings.append(ValidationIssue(ValidationCodes.META_MISSING_DOWNLOADED_AT, "Missing downloaded_at timestamp", ValidationStatus.WARNING, "metadata"))
        return errors, warnings, checks


class TimeframeRule(ValidationRule):
    def validate(self, dataset, config):
        errors, warnings, checks = [], [], 1
        timeframes = getattr(dataset, "timeframes", {}) if dataset is not None else {}
        if not isinstance(timeframes, dict):
            return [ValidationIssue(ValidationCodes.TF_MISSING_DICT, "Dataset contains no timeframes dictionary", ValidationStatus.FAILED, "timeframes")], warnings, checks
        checks += 1
        if not timeframes:
            errors.append(ValidationIssue(ValidationCodes.TF_EMPTY_COLLECTION, "At least one timeframe is required", ValidationStatus.FAILED, "timeframes"))
            return errors, warnings, checks
        seen: set[str] = set()
        for key, tf_data in timeframes.items():
            checks += 1
            name = key.value if hasattr(key, "value") else str(key)
            if name in seen:
                errors.append(ValidationIssue(ValidationCodes.TF_DUPLICATE, f"Duplicate timeframe detected: {name}", ValidationStatus.FAILED, "timeframes"))
            seen.add(name)
            checks += 1
            if not isinstance(tf_data, TimeframeData):
                errors.append(ValidationIssue(ValidationCodes.TF_INVALID_TYPE, f"Invalid timeframe container type for {name}", ValidationStatus.FAILED, "timeframes"))
                continue
            checks += 1
            dataframe = getattr(tf_data, "dataframe", None)
            if dataframe is None or dataframe.empty:
                errors.append(ValidationIssue(ValidationCodes.TF_EMPTY_DATAFRAME, f"DataFrame is empty or None for timeframe {name}", ValidationStatus.FAILED, "timeframes"))
            else:
                checks += 1
                if len(dataframe) <= 0:
                    errors.append(ValidationIssue(ValidationCodes.TF_INVALID_CANDLES_COUNT, f"Candles count must be > 0 for timeframe {name}", ValidationStatus.FAILED, "timeframes"))
        return errors, warnings, checks


# Retained as extension points for later component-level validation.
class ProfileRule(ValidationRule):
    def validate(self, dataset, config):
        return [], [], 0


class ScoreRule(ValidationRule):
    def validate(self, dataset, config):
        return [], [], 0


class DecisionRule(ValidationRule):
    def validate(self, dataset, config):
        return [], [], 0


class ReportRule(ValidationRule):
    def validate(self, dataset, config):
        return [], [], 0


class ValidationEngine:
    """Stateless validator for the MarketDataset boundary."""

    def __init__(self, rules: Optional[list[ValidationRule]] = None) -> None:
        self.logger = LoggerAdapter(base_logger, {"symbol": None, "status": None, "checks": 0, "warnings": 0, "errors": 0, "elapsed_ms": None, "operation": "init"})
        self.config = ValidationConfig()
        self.rules = rules if rules is not None else [MetadataRule(), TimeframeRule()]

    def register_rule(self, rule: ValidationRule) -> None:
        self.rules.append(rule)

    def validate_dataset(self, dataset: MarketDataset) -> ValidationResult:
        symbol = dataset.symbol if dataset and dataset.symbol else "UNKNOWN"
        started = time.perf_counter()
        errors: list[ValidationIssue] = []
        warnings: list[ValidationIssue] = []
        checks = 0
        try:
            for rule in self.rules:
                rule_errors, rule_warnings, rule_checks = rule.validate(dataset, self.config)
                errors.extend(rule_errors)
                warnings.extend(rule_warnings)
                checks += rule_checks
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            result = self._finalize_result(errors, warnings, checks, elapsed_ms)
            self.logger.extra.update({"symbol": symbol, "status": result.status.value, "checks": checks, "warnings": len(warnings), "errors": len(errors), "elapsed_ms": elapsed_ms, "operation": "validate_dataset"})
            self.logger.info("MarketDataset validation completed.")
            if self.config.STRICT_MODE and errors:
                raise DatasetValidationError(f"Dataset validation failed for {symbol} with {len(errors)} error(s).")
            return result
        except DatasetValidationError:
            raise
        except Exception as exc:
            raise ValidationEngineError(f"Unexpected error during dataset validation for {symbol}: {exc}") from exc

    def _finalize_result(self, errors, warnings, checks, elapsed_ms) -> ValidationResult:
        status = ValidationStatus.FAILED if errors else ValidationStatus.WARNING if warnings else ValidationStatus.PASSED
        passed = not errors
        issues = errors + warnings
        summary = [f"Validation Status: {status.value}", f"Total Checks: {checks}", f"Errors Encountered: {len(errors)}", f"Warnings Encountered: {len(warnings)}", f"Execution Time: {elapsed_ms:.2f}ms"]
        report = ValidationReport(checks, len(errors), len(warnings), passed, elapsed_ms, issues, summary)
        return ValidationResult(status, passed, warnings, errors, elapsed_ms, datetime.now(timezone.utc), checks, report)


# End Of File
