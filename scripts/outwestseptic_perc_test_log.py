#!/usr/bin/env python3
"""Out West Septic timed water-drop observation logger; no design classification."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
import math
from pathlib import Path
import statistics
import sys
from xml.sax.saxutils import escape

SOURCE_URL = "https://www.tceq.texas.gov/permitting/ossf/ossfadvice.html"
SCOPE = (
    "Observation record only. Ratios do not establish soil suitability, an approved "
    "loading rate, system selection, or permit compliance. A site evaluation and "
    "the applicable authority's requirements must guide those decisions."
)


def _number(value: float, name: str, *, allow_zero: bool = False) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite number")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite number") from exc
    if not math.isfinite(result) or result < 0 or (not allow_zero and result == 0):
        qualifier = "nonnegative" if allow_zero else "positive"
        raise ValueError(f"{name} must be finite and {qualifier}")
    return result


def _label(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 200:
        raise ValueError(f"{name} must contain 1 to 200 characters")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError(f"{name} must not contain control characters")
    return value.strip()


@dataclass(frozen=True)
class OutWestSepticPercHoleSummary:
    hole_id: str
    interval_minutes: float
    readings_in: tuple[float, ...]
    rates_min_per_in: tuple[float | None, ...] = ()
    average_rate: float | None = None
    median_rate: float | None = None

    def __post_init__(self) -> None:
        # Preserve old constructor arguments, but derive every result from the raw
        # observations so callers cannot create a contradictory or mutable record.
        interval = _number(self.interval_minutes, "interval")
        try:
            readings = tuple(_number(v, "water drop", allow_zero=True) for v in self.readings_in)
        except TypeError as exc:
            raise ValueError("readings_in must be a sequence of observations") from exc
        if not readings:
            raise ValueError("A hole summary requires at least one reading")
        rates = tuple(None if drop == 0 else interval / drop for drop in readings)
        positive = sorted(rate for rate in rates if rate is not None)
        if any(not math.isfinite(rate) or rate <= 0 for rate in positive):
            raise ValueError("Interval/drop ratio is outside the supported numeric range")
        middle = len(positive) // 2
        median = None
        if positive:
            median = positive[middle] if len(positive) % 2 else statistics.mean(positive[middle - 1:middle + 1])
        object.__setattr__(self, "hole_id", _label(self.hole_id, "hole ID"))
        object.__setattr__(self, "interval_minutes", interval)
        object.__setattr__(self, "readings_in", readings)
        object.__setattr__(self, "rates_min_per_in", rates)
        object.__setattr__(self, "average_rate", statistics.mean(positive) if positive else None)
        object.__setattr__(self, "median_rate", median)

    @property
    def zero_drop_count(self) -> int:
        return self.readings_in.count(0.0)


class OutWestSepticPercTestLogger:
    """Store observations without assigning a soil or treatment-system category."""

    def __init__(self, county: str = "County not recorded") -> None:
        self.county = _label(county, "county")
        self.holes: dict[str, list[float]] = {}

    def add_reading(self, hole_id: str, drop_inches: float) -> None:
        hole_id = _label(hole_id, "hole ID")
        drop = _number(drop_inches, "water drop", allow_zero=True)
        self.holes.setdefault(hole_id, []).append(drop)

    def hole_summary(self, hole_id: str, interval_minutes: float) -> OutWestSepticPercHoleSummary:
        interval = _number(interval_minutes, "interval")
        hole_id = _label(hole_id, "hole ID")
        if hole_id not in self.holes or not self.holes[hole_id]:
            raise ValueError(f"No readings recorded for hole {hole_id}")
        return OutWestSepticPercHoleSummary(hole_id, interval, tuple(self.holes[hole_id]))

    def all_summaries(self, interval_minutes: float) -> list[OutWestSepticPercHoleSummary]:
        return [self.hole_summary(hole, interval_minutes) for hole in sorted(self.holes)]

    @staticmethod
    def classify(rate: float) -> str:
        raise ValueError("Rate-based system classification has been removed; use a qualified site evaluation.")


@dataclass(frozen=True)
class OutWestSepticPercReport:
    site: str
    county: str
    test_date: datetime
    interval_minutes: float
    summaries: tuple[OutWestSepticPercHoleSummary, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "site", _label(self.site, "site"))
        object.__setattr__(self, "county", _label(self.county, "county"))
        object.__setattr__(self, "interval_minutes", _number(self.interval_minutes, "interval"))
        object.__setattr__(self, "summaries", tuple(self.summaries))
        if not isinstance(self.test_date, datetime):
            raise ValueError("test_date must be a datetime")
        if not self.summaries:
            raise ValueError("A report requires at least one hole")
        if any(summary.interval_minutes != self.interval_minutes for summary in self.summaries):
            raise ValueError("Every hole must use the report's interval")

    def render_text(self) -> str:
        rows = [
            "Out West Septic - water-drop observation report",
            f"Site: {self.site}", f"County: {self.county}",
            f"Report timestamp: {self.test_date.isoformat()}",
            f"Recorded interval: {_format(self.interval_minutes)} minutes",
            SCOPE, "",
            "Each ratio = interval minutes / observed drop inches.",
            "Zero drop is retained; its ratio is undefined, not zero.",
            "Mean/median include positive-drop readings only; they are not design rates.",
        ]
        for summary in self.summaries:
            rows.extend([
                "", f"Hole: {summary.hole_id}",
                f"Readings: {len(summary.readings_in)}; zero drops: {summary.zero_drop_count}",
                f"Positive-drop mean: {_format(summary.average_rate)} min/in",
                f"Positive-drop median: {_format(summary.median_rate)} min/in",
            ])
            for index, (drop, rate) in enumerate(zip(summary.readings_in, summary.rates_min_per_in), 1):
                rows.append(f"  {index}: drop {_format(drop)} in; ratio {_format(rate)} min/in")
        rows.extend(["", f"Background: {SOURCE_URL}", "Project: https://outwestseptic.com"])
        return "\n".join(rows)


# Public names retained for callers of the original prototype.
PercHoleSummary = OutWestSepticPercHoleSummary
PercReport = OutWestSepticPercReport


def _format(value: float | None) -> str:
    return "undefined" if value is None else format(value, ".6g")


def _export_pdf(report: OutWestSepticPercReport, path: str | Path) -> bool:
    """Create an exclusive new PDF; raise on missing dependency or export failure."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError as exc:
        raise RuntimeError("PDF export requires ReportLab; install requirements.txt first") from exc

    destination = Path(path)
    if destination.exists():
        raise FileExistsError(f"Refusing to overwrite existing report: {destination}")
    styles = getSampleStyleSheet()
    paragraph = lambda value, style="BodyText": Paragraph(escape(str(value)), styles[style])
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter, rightMargin=0.75 * inch, leftMargin=0.75 * inch,
        topMargin=0.65 * inch, bottomMargin=0.65 * inch,
        title="Out West Septic water-drop observation report", author="Out West Septic project",
    )
    story = [
        paragraph("Out West Septic water-drop observation report", "Title"),
        paragraph(f"Site: {report.site}"),
        paragraph(f"County: {report.county}"),
        paragraph(f"Report timestamp: {report.test_date.isoformat()}"),
        paragraph(f"Recorded interval: {_format(report.interval_minutes)} minutes"),
        Spacer(1, 10), paragraph(SCOPE),
        paragraph("Ratios are minutes / observed drop inches. Zero-drop ratios are undefined. "
                  "Mean and median include positive-drop readings only; they are not design rates."),
    ]
    for summary in report.summaries:
        story.extend([
            Spacer(1, 12), paragraph(f"Hole: {summary.hole_id}", "Heading2"),
            paragraph(f"Readings: {len(summary.readings_in)}; zero drops: {summary.zero_drop_count}. "
                      f"Positive-drop mean: {_format(summary.average_rate)} min/in; "
                      f"median: {_format(summary.median_rate)} min/in."),
        ])
        rows = [["Reading", "Drop (inches)", "Ratio (min/inch)"]]
        rows.extend([
            str(index), _format(drop), _format(rate)
        ] for index, (drop, rate) in enumerate(zip(summary.readings_in, summary.rates_min_per_in), 1))
        table = Table(rows, colWidths=[1.0 * inch, 2.5 * inch, 3.5 * inch], repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E7EDF1")),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(table)
    story.extend([Spacer(1, 12), paragraph(f"Background: {SOURCE_URL}"),
                  paragraph("Project: https://outwestseptic.com")])

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.drawString(0.75 * inch, 0.3 * inch, f"Observation record - page {document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    # Build before creating the destination; exclusive creation prevents races/overwrites.
    with destination.open("xb") as output:
        output.write(buffer.getvalue())
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", default="Site not recorded")
    parser.add_argument("--county", default="County not recorded")
    parser.add_argument("--interval", type=float, required=True, help="Actual observation interval in minutes")
    parser.add_argument("--pdf", type=Path, help="New PDF path (existing files are never overwritten)")
    parser.add_argument("--demo", action="store_true", help="Use explicitly synthetic observations")
    args = parser.parse_args(argv)
    try:
        interval = _number(args.interval, "interval")
        site = _label(args.site, "site")
        logger = OutWestSepticPercTestLogger(args.county)
        if args.demo:
            site = f"SYNTHETIC DEMO: {site}"
            for drop in (1.0, 0.5, 0.0):
                logger.add_reading("Demo hole", drop)
        else:
            count = int(input("Number of holes: "))
            if count < 1:
                raise ValueError("At least one hole is required")
            for number in range(1, count + 1):
                hole_id = _label(input(f"Hole {number} label: "), "hole ID")
                if hole_id in logger.holes:
                    raise ValueError("Each hole must have a distinct label")
                raw = input("Observed drops in inches, separated by commas (zero is allowed): ")
                for item in raw.split(","):
                    logger.add_reading(hole_id, float(item.strip()))
        summaries = tuple(logger.hole_summary(hole, interval) for hole in logger.holes)
        report = OutWestSepticPercReport(site, logger.county, datetime.now(timezone.utc), interval, summaries)
        print(report.render_text())
        if args.pdf:
            _export_pdf(report, args.pdf)
            print(f"PDF created: {args.pdf}")
        return 0
    except (ValueError, RuntimeError, OSError, EOFError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Cancelled; no report exported.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
