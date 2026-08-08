"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module       : reports.html_report
Version      : 1.0.0
Status       : ORION Production V1.0 INITIAL
===============================================================================

HTML Report Renderer responsible solely for transforming a FullReport instance
into a clean, responsive HTML string representation using pure string building
without external templating engines, file I/O, or path operations.
===============================================================================
"""

from __future__ import annotations

import html
import logging
from typing import Any, Optional

from reports.report_models import FullReport

base_logger = logging.getLogger(__name__)


# =============================================================================
# Custom Exceptions
# =============================================================================

class HtmlReportRendererError(Exception):
    """Base exception class for all HTML report rendering related errors."""
    pass


# =============================================================================
# Logger Adapter
# =============================================================================

class LoggerAdapter(logging.LoggerAdapter):
    """Custom LoggerAdapter injecting HTML renderer operation context attributes into log entries."""

    def process(self, msg: str, kwargs: Any) -> tuple[str, dict[str, Any]]:
        context = self.extra or {}
        context_str = " | ".join(f"{k}={v}" for k, v in context.items() if v is not None)
        formatted_msg = f"[{context_str}] {msg}" if context_str else msg
        return formatted_msg, kwargs


# =============================================================================
# HTML Report Renderer
# =============================================================================

class HtmlReportRenderer:
    """
    Stateless HTML report renderer converting FullReport domain models into
    fully structured HTML strings via pure string manipulation.
    """

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        self._logger_instance = logger if logger is not None else base_logger

        self._logger = LoggerAdapter(
            self._logger_instance,
            {
                "component": "HtmlReportRenderer",
                "operation": "init",
            },
        )
        self._logger.info("HtmlReportRenderer initialized successfully.")

    def _get_logger(self, operation: Optional[str] = None) -> LoggerAdapter:
        return LoggerAdapter(
            self._logger_instance,
            {
                "component": "HtmlReportRenderer",
                "operation": operation,
            },
        )

    # -------------------------------------------------------------------------
    # Public Methods
    # -------------------------------------------------------------------------

    def render(self, report: FullReport) -> str:
        """
        Renders a FullReport instance into a clean, standalone HTML string.
        """
        logger = self._get_logger(operation="render")
        logger.info(f"Rendering HTML report: '{report.metadata.report_name}'")

        try:
            html_parts: list[str] = []

            # 1. Document Head & Stylesheet
            html_parts.append("<!DOCTYPE html>")
            html_parts.append("<html lang=\"en\">")
            html_parts.append("<head>")
            html_parts.append("<meta charset=\"UTF-8\">")
            html_parts.append(f"<title>{html.escape(report.metadata.report_name)} - ORION</title>")
            html_parts.append("<style>")
            html_parts.append(
                "body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; "
                "margin: 0; padding: 20px; background-color: #f4f6f9; color: #333; }"
            )
            html_parts.append(
                ".container { max-width: 1200px; margin: 0 auto; background: #fff; "
                "padding: 30px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }"
            )
            html_parts.append("h1, h2 { color: #1a202c; border-bottom: 2px solid #e2e8f0; padding-bottom: 10px; }")
            html_parts.append(".metadata-box { background: #edf2f7; padding: 15px; border-radius: 6px; margin-bottom: 25px; display: flex; flex-wrap: wrap; gap: 20px; }")
            html_parts.append(".metadata-item { font-size: 14px; color: #4a5568; }")
            html_parts.append(".metadata-item strong { color: #2d3748; }")
            html_parts.append(".summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 30px; }")
            html_parts.append(".summary-card { background: #ebf8ff; border: 1px solid #bee3f8; padding: 20px; border-radius: 6px; text-align: center; }")
            html_parts.append(".summary-card.buy { background: #f0fff4; border-color: #c6f6d5; }")
            html_parts.append(".summary-card.sell { background: #fff5f5; border-color: #fed7d7; }")
            html_parts.append(".summary-card h3 { margin: 0 0 10px 0; font-size: 14px; color: #4a5568; border: none; padding: 0; }")
            html_parts.append(".summary-card .value { font-size: 24px; font-weight: bold; color: #2b6cb0; }")
            html_parts.append(".summary-card.buy .value { color: #2f855a; }")
            html_parts.append(".summary-card.sell .value { color: #c53030; }")
            html_parts.append("table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 14px; }")
            html_parts.append("th, td { padding: 12px 15px; text-align: left; border-bottom: 1px solid #e2e8f0; }")
            html_parts.append("th { background-color: #f7fafc; color: #2d3748; font-weight: 600; text-transform: uppercase; font-size: 12px; letter-spacing: 0.05em; }")
            html_parts.append("tr:hover { background-color: #f8fafc; }")
            html_parts.append(".badge { display: inline-block; padding: 4px 8px; border-radius: 4px; font-weight: 600; font-size: 12px; }")
            html_parts.append(".badge-buy, .badge-favorable { background: #c6f6d5; color: #22543d; }")
            html_parts.append(".badge-sell, .badge-unfavorable { background: #fed7d7; color: #742a2a; }")
            html_parts.append(".badge-hold, .badge-wait { background: #e2e8f0; color: #4a5568; }")
            html_parts.append("pre { background: #2d3748; color: #e2e8f0; padding: 10px; border-radius: 4px; font-size: 12px; overflow-x: auto; margin: 5px 0 0 0; }")
            html_parts.append("</style>")
            html_parts.append("</head>")

            # 2. Body Container Start
            html_parts.append("<body>")
            html_parts.append("<div class=\"container\">")

            # 3. Header Section
            html_parts.append(f"<h1>{html.escape(report.metadata.report_name)}</h1>")
            html_parts.append("<div class=\"metadata-box\">")
            html_parts.append(f"<div class=\"metadata-item\"><strong>Generated At:</strong> {html.escape(str(report.metadata.generated_at))}</div>")
            html_parts.append(f"<div class=\"metadata-item\"><strong>Version:</strong> {html.escape(report.metadata.project_version)}</div>")
            html_parts.append(f"<div class=\"metadata-item\"><strong>Execution Time:</strong> {report.metadata.execution_time_ms:.2f} ms</div>")
            html_parts.append("</div>")

            # 4. Summary Table / Cards Section
            html_parts.append("<h2>Execution Summary</h2>")
            html_parts.append("<div class=\"summary-grid\">")
            html_parts.append(f"<div class=\"summary-card\"><h3>Total Symbols</h3><div class=\"value\">{report.summary.total_symbols}</div></div>")
            html_parts.append(f"<div class=\"summary-card buy\"><h3>Favorable / Buy</h3><div class=\"value\">{report.summary.buy_count}</div></div>")
            html_parts.append(f"<div class=\"summary-card sell\"><h3>Unfavorable / Sell</h3><div class=\"value\">{report.summary.sell_count}</div></div>")
            html_parts.append(f"<div class=\"summary-card\"><h3>Wait / Hold</h3><div class=\"value\">{report.summary.hold_count}</div></div>")
            html_parts.append("</div>")

            # 5. Symbols Detailed Table Section
            html_parts.append("<h2>Symbol Breakdown</h2>")
            html_parts.append("<table>")
            html_parts.append("<thead>")
            html_parts.append("<tr>")
            html_parts.append("<th>Symbol</th>")
            html_parts.append("<th>Decision</th>")
            html_parts.append("<th>Score</th>")
            html_parts.append("<th>Confidence</th>")
            html_parts.append("<th>Timeframes</th>")
            html_parts.append("</tr>")
            html_parts.append("</thead>")
            html_parts.append("<tbody>")

            if not report.symbols:
                html_parts.append("<tr><td colspan=\"5\" style=\"text-align: center; color: #718096;\">No symbol results recorded.</td></tr>")
            else:
                for sym in report.symbols:
                    decision_lower = sym.decision.lower()
                    badge_class = f"badge badge-{decision_lower}" if decision_lower in {"buy", "sell", "hold", "favorable", "unfavorable", "wait"} else "badge badge-hold"
                    
                    timeframes_str = ", ".join(sym.timeframes) if sym.timeframes else "-"

                    html_parts.append("<tr>")
                    html_parts.append(f"<td><strong>{html.escape(sym.symbol)}</strong></td>")
                    html_parts.append(f"<td><span class=\"{badge_class}\">{html.escape(sym.decision)}</span></td>")
                    html_parts.append(f"<td>{sym.score:.2f}</td>")
                    html_parts.append(f"<td>{sym.confidence:.1f}%</td>")
                    html_parts.append(f"<td>{html.escape(timeframes_str)}</td>")
                    html_parts.append("</tr>")

                    # If details dictionary is non-empty, render additional row
                    if sym.details:
                        details_items = [f"{k}: {v}" for k, v in sym.details.items() if v is not None and v != [] and v != {}]
                        if details_items:
                            details_text = "\n".join(details_items)
                            html_parts.append("<tr>")
                            html_parts.append("<td colspan=\"5\" style=\"background-color: #fafbfc; padding-top: 0;\">")
                            html_parts.append("<div style=\"font-size: 12px; color: #4a5568; margin-bottom: 4px;\"><strong>Details:</strong></div>")
                            html_parts.append(f"<pre>{html.escape(details_text)}</pre>")
                            html_parts.append("</td>")
                            html_parts.append("</tr>")

            html_parts.append("</tbody>")
            html_parts.append("</table>")

            # 6. Container & Document Closure
            html_parts.append("</div>")
            html_parts.append("</body>")
            html_parts.append("</html>")

            full_html = "".join(html_parts)
            logger.info("HTML report rendered successfully.")
            return full_html

        except Exception as e:
            logger.error(f"Failed to render HTML report: {e}")
            raise HtmlReportRendererError(f"Failed to render HTML report: {e}") from e


# =============================================================================
# End Of File
# =============================================================================