"""JSON report renderer with canonical ReportResult support."""
from __future__ import annotations

import json
from dataclasses import fields, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from models.report import ReportResult


class JsonReportRendererError(Exception):
    """Base exception for JSON report rendering failures."""


class JsonReportRenderer:
    """Render canonical reports and remain compatible with legacy dataclass reports during migration."""

    def render(self, report: ReportResult | Any, indent: int = 4) -> str:
        if report is None:
            raise JsonReportRendererError("render requires a report object.")
        try:
            return json.dumps(
                self._to_serializable(report),
                ensure_ascii=False,
                indent=indent,
                sort_keys=True,
            )
        except Exception as exc:
            raise JsonReportRendererError(
                f"Failed to render JSON report: {exc}"
            ) from exc

    @classmethod
    def _to_serializable(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, datetime):
            return value.isoformat()
        if is_dataclass(value):
            return {
                field.name: cls._to_serializable(getattr(value, field.name))
                for field in fields(value)
            }
        if isinstance(value, dict):
            return {
                str(key): cls._to_serializable(item)
                for key, item in value.items()
            }
        if isinstance(value, (list, tuple, set, frozenset)):
            return [cls._to_serializable(item) for item in value]
        if hasattr(value, "tolist"):
            try:
                return value.tolist()
            except Exception:
                pass
        if isinstance(value, (str, int, float, bool)):
            return value
        return str(value)


__all__ = ["JsonReportRenderer", "JsonReportRendererError"]
