"""Canonical HTML report renderer for ORION ReportResult."""
from __future__ import annotations

import html
from dataclasses import fields, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from models.report import ReportResult


class HtmlReportRendererError(Exception):
    """Base exception for HTML report rendering failures."""


class HtmlReportRenderer:
    """Render the canonical ReportResult without depending on legacy report models."""

    def render(self, report: ReportResult) -> str:
        if not isinstance(report, ReportResult):
            raise HtmlReportRendererError("render requires a ReportResult.")
        try:
            metadata = report.metadata
            decision = self._value(getattr(report.decision, "decision", None), "WAIT")
            score = self._value(
                getattr(report.score, "total_score", None),
                getattr(report.score, "score", "N/A"),
            )
            confidence = getattr(report.decision, "confidence", "N/A")
            timeframes = self._extract_timeframes(report)

            sections = [
                "<!DOCTYPE html>",
                '<html lang="en">',
                "<head>",
                '<meta charset="UTF-8">',
                f"<title>{html.escape(metadata.report_name)} - ORION</title>",
                "<style>",
                "body{font-family:Arial,sans-serif;margin:0;padding:24px;background:#f4f6f9;color:#222}",
                ".container{max-width:1100px;margin:auto;background:#fff;padding:28px;border-radius:8px}",
                ".meta{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;background:#f7fafc;padding:16px;border-radius:6px}",
                ".card{margin-top:20px;padding:18px;border:1px solid #e2e8f0;border-radius:6px}",
                "table{width:100%;border-collapse:collapse}",
                "th,td{text-align:left;padding:9px;border-bottom:1px solid #e2e8f0;vertical-align:top}",
                "th{width:220px;background:#f7fafc}",
                "pre{white-space:pre-wrap;background:#f7fafc;padding:12px;border-radius:4px}",
                ".warning{padding:10px;background:#fff8e1;border:1px solid #f6d365;border-radius:4px;margin-top:8px}",
                "</style>",
                "</head>",
                "<body>",
                '<div class="container">',
                f"<h1>{html.escape(metadata.report_name)}</h1>",
                '<div class="meta">',
                f"<div><strong>Symbol</strong><br>{html.escape(report.symbol)}</div>",
                f"<div><strong>Version</strong><br>{html.escape(metadata.project_version)}</div>",
                f"<div><strong>Generated</strong><br>{html.escape(report.generated_at.isoformat())}</div>",
                f"<div><strong>Execution Time</strong><br>{metadata.execution_time_ms:.2f} ms</div>",
                "</div>",
                '<div class="card"><h2>Decision</h2><table>',
                f"<tr><th>Decision</th><td>{html.escape(str(decision))}</td></tr>",
                f"<tr><th>Score</th><td>{html.escape(str(score))}</td></tr>",
                f"<tr><th>Confidence</th><td>{html.escape(str(confidence))}</td></tr>",
                f"<tr><th>Timeframes</th><td>{html.escape(timeframes)}</td></tr>",
                "</table></div>",
            ]

            if report.summary:
                sections.extend([
                    '<div class="card"><h2>Summary</h2><ul>',
                    *[f"<li>{html.escape(str(item))}</li>" for item in report.summary],
                    "</ul></div>",
                ])

            if report.highlights:
                sections.extend([
                    '<div class="card"><h2>Highlights</h2><ul>',
                    *[f"<li>{html.escape(str(item))}</li>" for item in report.highlights],
                    "</ul></div>",
                ])

            if report.warnings:
                sections.append('<div class="card"><h2>Warnings</h2>')
                sections.extend(
                    f'<div class="warning">{html.escape(str(item))}</div>'
                    for item in report.warnings
                )
                sections.append("</div>")

            sections.extend([
                '<div class="card"><h2>Canonical Results</h2>',
                f"<pre>{html.escape(self._pretty_dump(report))}</pre>",
                "</div>",
                "</div>",
                "</body>",
                "</html>",
            ])
            return "".join(sections)
        except Exception as exc:
            raise HtmlReportRendererError(
                f"Failed to render HTML report: {exc}"
            ) from exc

    @staticmethod
    def _value(value: Any, fallback: Any) -> Any:
        return fallback if value is None else value.value if isinstance(value, Enum) else value

    @staticmethod
    def _extract_timeframes(report: ReportResult) -> str:
        for source in (report.analysis, report.profile):
            if source is None:
                continue
            value = getattr(source, "timeframes", None)
            if value:
                return ", ".join(str(item) for item in value)
        return "-"

    @classmethod
    def _pretty_dump(cls, report: ReportResult) -> str:
        def normalize(value: Any) -> Any:
            if isinstance(value, Enum):
                return value.value
            if isinstance(value, datetime):
                return value.isoformat()
            if is_dataclass(value):
                return {
                    field.name: normalize(getattr(value, field.name))
                    for field in fields(value)
                }
            if isinstance(value, (list, tuple, set, frozenset)):
                return [normalize(item) for item in value]
            if isinstance(value, dict):
                return {str(k): normalize(v) for k, v in value.items()}
            return value

        import json
        return json.dumps(normalize(report), ensure_ascii=False, indent=2, default=str)


__all__ = ["HtmlReportRenderer", "HtmlReportRendererError"]
