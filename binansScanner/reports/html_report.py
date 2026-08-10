"""HTML report renderer with canonical ReportResult support."""
from __future__ import annotations

import html
import json
from dataclasses import fields, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from models.report import ReportResult


class HtmlReportRendererError(Exception):
    """Base exception for HTML report rendering failures."""


class HtmlReportRenderer:
    """Render canonical ReportResult while allowing legacy reports during controlled migration."""

    def render(self, report: ReportResult | Any) -> str:
        if report is None:
            raise HtmlReportRendererError("render requires a report object.")
        try:
            metadata = getattr(report, "metadata", None)
            report_name = str(getattr(metadata, "report_name", "ORION Report"))
            project_version = str(getattr(metadata, "project_version", ""))
            execution_time = float(getattr(metadata, "execution_time_ms", 0.0) or 0.0)
            generated_at = getattr(report, "generated_at", None)
            symbol = getattr(report, "symbol", None)

            if isinstance(report, ReportResult):
                decision = self._value(getattr(report.decision, "decision", None), "WAIT")
                score = self._value(
                    getattr(report.score, "total_score", None),
                    getattr(report.score, "score", "N/A"),
                )
                confidence = getattr(report.decision, "confidence", "N/A")
                timeframes = self._extract_timeframes(report)
                summary = report.summary
                highlights = report.highlights
                warnings = report.warnings
            else:
                symbols = list(getattr(report, "symbols", ()) or ())
                first = symbols[0] if symbols else None
                symbol = getattr(first, "symbol", "UNKNOWN") if first else "UNKNOWN"
                decision = getattr(first, "decision", "WAIT") if first else "WAIT"
                score = getattr(first, "score", "N/A") if first else "N/A"
                confidence = getattr(first, "confidence", "N/A") if first else "N/A"
                timeframes = ", ".join(str(item) for item in (getattr(first, "timeframes", ()) or ())) if first else "-"
                summary_obj = getattr(report, "summary", None)
                summary = tuple(
                    f"Total symbols: {getattr(summary_obj, 'total_symbols', 0)}",
                    f"Buy: {getattr(summary_obj, 'buy_count', 0)}",
                    f"Sell: {getattr(summary_obj, 'sell_count', 0)}",
                    f"Hold: {getattr(summary_obj, 'hold_count', 0)}",
                ) if summary_obj else ()
                highlights = ()
                warnings = ()
                if first:
                    warnings = tuple(getattr(first, "details", {}).get("warnings", ()) or ())

            generated_text = (
                generated_at.isoformat()
                if isinstance(generated_at, datetime)
                else str(generated_at or getattr(metadata, "generated_at", ""))
            )

            sections = [
                "<!DOCTYPE html>",
                '<html lang="en">',
                "<head>",
                '<meta charset="UTF-8">',
                f"<title>{html.escape(report_name)} - ORION</title>",
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
                f"<h1>{html.escape(report_name)}</h1>",
                '<div class="meta">',
                f"<div><strong>Symbol</strong><br>{html.escape(str(symbol or 'UNKNOWN'))}</div>",
                f"<div><strong>Version</strong><br>{html.escape(project_version)}</div>",
                f"<div><strong>Generated</strong><br>{html.escape(generated_text)}</div>",
                f"<div><strong>Execution Time</strong><br>{execution_time:.2f} ms</div>",
                "</div>",
                '<div class="card"><h2>Decision</h2><table>',
                f"<tr><th>Decision</th><td>{html.escape(str(decision))}</td></tr>",
                f"<tr><th>Score</th><td>{html.escape(str(score))}</td></tr>",
                f"<tr><th>Confidence</th><td>{html.escape(str(confidence))}</td></tr>",
                f"<tr><th>Timeframes</th><td>{html.escape(timeframes or '-')}</td></tr>",
                "</table></div>",
            ]

            if summary:
                sections.extend([
                    '<div class="card"><h2>Summary</h2><ul>',
                    *[f"<li>{html.escape(str(item))}</li>" for item in summary],
                    "</ul></div>",
                ])
            if highlights:
                sections.extend([
                    '<div class="card"><h2>Highlights</h2><ul>',
                    *[f"<li>{html.escape(str(item))}</li>" for item in highlights],
                    "</ul></div>",
                ])
            if warnings:
                sections.append('<div class="card"><h2>Warnings</h2>')
                sections.extend(
                    f'<div class="warning">{html.escape(str(item))}</div>'
                    for item in warnings
                )
                sections.append("</div>")

            sections.extend([
                '<div class="card"><h2>Report Data</h2>',
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

    @staticmethod
    def _pretty_dump(report: Any) -> str:
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

        return json.dumps(normalize(report), ensure_ascii=False, indent=2, default=str)


__all__ = ["HtmlReportRenderer", "HtmlReportRendererError"]
