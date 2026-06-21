#!/usr/bin/env python3
"""Plot benchmark execution time from reports/benchmarks/benchmark_results.csv.

Inputs by default:
  reports/benchmarks/benchmark_results.csv

Outputs by default:
  reports/plots/benchmark_execution_time.svg

The plot uses grouped bars: each x-axis bin is one benchmark and each colored
bar is one RTL version.  It intentionally uses only the Python standard library
so the benchmark plot can be regenerated without matplotlib/pandas.
"""

from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

DEFAULT_INPUT = Path("reports/benchmarks/benchmark_results.csv")
DEFAULT_OUTPUT = Path("reports/plots/benchmark_execution_time.svg")
DEFAULT_VERSION_ORDER = ("baseline", "no_mul_forwarding", "no_alu_forwarding", "no_alu_mul_forwarding")
DEFAULT_BENCHMARK_ORDER = ("vvadd", "multiply", "median", "sort", "rsort", "mm", "dhrystone")
COLORS = {
    # Keep these in sync with scripts/plot-utilization.py.
    "baseline": "#2563eb",
    "no_mul_forwarding": "#dc2626",
    "no_alu_forwarding": "#16a34a",
    "no_alu_mul_forwarding": "#9333ea",
    # Accept hyphenated names too, for hand-written CSVs.
    "no-mul-forwarding": "#dc2626",
    "no-alu-forwarding": "#16a34a",
    "no-alu-mul-forwarding": "#9333ea",
}
FALLBACK_COLORS = ["#ea580c", "#0891b2", "#4f46e5", "#be123c"]
DISPLAY_NAMES = {
    "baseline": "Baseline",
    "no_mul_forwarding": "No MUL fwd",
    "no_alu_forwarding": "No ALU fwd",
    "no_alu_mul_forwarding": "No ALU+MUL fwd",
    "no-mul-forwarding": "No MUL fwd",
    "no-alu-forwarding": "No ALU fwd",
    "no-alu-mul-forwarding": "No ALU+MUL fwd",
}


@dataclass(frozen=True)
class BenchmarkRow:
    version: str
    benchmark: str
    status: str
    roi_time_ns: float
    roi_cycles: int
    clock_period_ns: float


def parse_float(value: str, field: str, row_num: int) -> float:
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"row {row_num}: invalid {field}={value!r}") from exc


def parse_int(value: str, field: str, row_num: int) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"row {row_num}: invalid {field}={value!r}") from exc


def read_benchmark_csv(path: Path, include_failed: bool = False) -> list[BenchmarkRow]:
    if not path.exists():
        raise FileNotFoundError(f"missing benchmark CSV: {path}")

    rows: list[BenchmarkRow] = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {"version", "benchmark", "status", "roi_cycles", "clock_period_ns", "roi_time_ns"}
        missing = required.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path} is missing required columns: {', '.join(sorted(missing))}")
        for row_num, row in enumerate(reader, start=2):
            status = (row.get("status") or "").strip()
            if status != "PASS" and not include_failed:
                continue
            roi_time_ns = parse_float(row["roi_time_ns"], "roi_time_ns", row_num)
            if roi_time_ns < 0 and not include_failed:
                continue
            rows.append(
                BenchmarkRow(
                    version=(row.get("version") or "").strip(),
                    benchmark=(row.get("benchmark") or "").strip(),
                    status=status,
                    roi_time_ns=roi_time_ns,
                    roi_cycles=parse_int(row["roi_cycles"], "roi_cycles", row_num),
                    clock_period_ns=parse_float(row["clock_period_ns"], "clock_period_ns", row_num),
                )
            )
    if not rows:
        raise ValueError(f"{path} did not contain any plottable benchmark rows")
    return rows


def ordered_unique(values: Iterable[str], preferred_order: Iterable[str]) -> list[str]:
    seen = set(values)
    ordered = [item for item in preferred_order if item in seen]
    ordered.extend(item for item in values if item not in ordered)
    return ordered


def fmt_us(value_us: float) -> str:
    if value_us >= 100:
        return f"{value_us:.0f}"
    if value_us >= 10:
        return f"{value_us:.1f}".rstrip("0").rstrip(".")
    return f"{value_us:.2f}".rstrip("0").rstrip(".")


def fmt_tick(value_us: float) -> str:
    if value_us >= 100:
        return f"{value_us:.0f}"
    if value_us >= 10:
        return f"{value_us:.0f}"
    return f"{value_us:.1f}".rstrip("0").rstrip(".")


def nice_y_max(max_value: float) -> float:
    if max_value <= 0:
        return 1.0
    raw = max_value * 1.18
    exponent = math.floor(math.log10(raw))
    fraction = raw / (10 ** exponent)
    if fraction <= 1:
        nice_fraction = 1
    elif fraction <= 2:
        nice_fraction = 2
    elif fraction <= 5:
        nice_fraction = 5
    else:
        nice_fraction = 10
    return nice_fraction * (10 ** exponent)


def svg_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def display_name(version: str) -> str:
    return DISPLAY_NAMES.get(version, version.replace("_", " ").replace("-", " ").title())


def write_svg(rows: list[BenchmarkRow], svg_path: Path, title: str, metric: str) -> None:
    svg_path.parent.mkdir(parents=True, exist_ok=True)

    versions = ordered_unique([row.version for row in rows], DEFAULT_VERSION_ORDER)
    benchmarks = ordered_unique([row.benchmark for row in rows], DEFAULT_BENCHMARK_ORDER)
    by_key = {(row.version, row.benchmark): row for row in rows}

    width = 1280
    height = 720
    margin_left = 105
    margin_right = 55
    margin_top = 98
    margin_bottom = 132
    plot_w = width - margin_left - margin_right
    plot_h = height - margin_top - margin_bottom

    values_us = [row.roi_time_ns / 1000.0 for row in rows]
    y_max = nice_y_max(max(values_us))

    group_w = plot_w / len(benchmarks)
    bar_gap = 5
    bars_total_max = group_w * 0.78
    bar_w = min(34.0, (bars_total_max - (len(versions) - 1) * bar_gap) / max(len(versions), 1))
    bar_w = max(bar_w, 10.0)
    bars_total = len(versions) * bar_w + (len(versions) - 1) * bar_gap

    def x_for(i: int, j: int) -> float:
        return margin_left + i * group_w + (group_w - bars_total) / 2 + j * (bar_w + bar_gap)

    def y_for(value_us: float) -> float:
        return margin_top + plot_h - (value_us / y_max) * plot_h

    tick_count = 5
    ticks = [y_max * i / tick_count for i in range(tick_count + 1)]

    parts: list[str] = []
    parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">')
    parts.append('<rect width="100%" height="100%" fill="#ffffff"/>')
    parts.append('<style>text{font-family:Inter,Arial,sans-serif;fill:#111827}.title{font-size:30px;font-weight:700}.subtitle{font-size:15px;fill:#4b5563}.axis{font-size:15px;font-weight:600;fill:#374151}.tick{font-size:13px;fill:#6b7280}.label{font-size:11px;fill:#111827}.legend{font-size:14px}.grid{stroke:#e5e7eb;stroke-width:1}.axisline{stroke:#374151;stroke-width:1.5}</style>')
    parts.append(f'<text class="title" x="{width/2}" y="38" text-anchor="middle">{svg_escape(title)}</text>')
    parts.append(f'<text class="subtitle" x="{width/2}" y="64" text-anchor="middle">Grouped by benchmark; colors match the utilization plot RTL versions</text>')

    for tick in ticks:
        y = y_for(tick)
        parts.append(f'<line class="grid" x1="{margin_left}" y1="{y:.1f}" x2="{width-margin_right}" y2="{y:.1f}"/>')
        parts.append(f'<text class="tick" x="{margin_left-10}" y="{y+4:.1f}" text-anchor="end">{fmt_tick(tick)}</text>')
    parts.append(f'<line class="axisline" x1="{margin_left}" y1="{margin_top}" x2="{margin_left}" y2="{margin_top+plot_h}"/>')
    parts.append(f'<line class="axisline" x1="{margin_left}" y1="{margin_top+plot_h}" x2="{width-margin_right}" y2="{margin_top+plot_h}"/>')
    parts.append(f'<text class="axis" x="28" y="{margin_top+plot_h/2}" text-anchor="middle" transform="rotate(-90 28 {margin_top+plot_h/2})">Execution time, {svg_escape(metric)} (µs)</text>')
    parts.append(f'<text class="axis" x="{margin_left+plot_w/2}" y="{height-28}" text-anchor="middle">Benchmark</text>')

    for i, benchmark in enumerate(benchmarks):
        center_x = margin_left + i * group_w + group_w / 2
        parts.append(f'<text class="axis" x="{center_x:.1f}" y="{margin_top+plot_h+35}" text-anchor="middle">{svg_escape(benchmark)}</text>')
        for j, version in enumerate(versions):
            row = by_key.get((version, benchmark))
            if row is None:
                continue
            value_us = row.roi_time_ns / 1000.0
            x = x_for(i, j)
            y = y_for(value_us)
            h = margin_top + plot_h - y
            color = COLORS.get(version, FALLBACK_COLORS[j % len(FALLBACK_COLORS)])
            parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" fill="{color}" rx="3"/>')
            # Keep labels compact; skip tiny bars where the value would collide with the x-axis.
            label_y = max(y - 7, margin_top + 12)
            parts.append(f'<text class="label" x="{x+bar_w/2:.1f}" y="{label_y:.1f}" text-anchor="middle" transform="rotate(-35 {x+bar_w/2:.1f} {label_y:.1f})">{fmt_us(value_us)}</text>')

    legend_x = margin_left
    legend_y = height - 56
    legend_step = 230
    for j, version in enumerate(versions):
        x = legend_x + j * legend_step
        y = legend_y
        if x + 190 > width - margin_right:
            x = legend_x + (j % 2) * 330
            y = legend_y + 24 * (j // 2)
        color = COLORS.get(version, FALLBACK_COLORS[j % len(FALLBACK_COLORS)])
        parts.append(f'<rect x="{x}" y="{y-13}" width="16" height="16" fill="{color}" rx="2"/>')
        parts.append(f'<text class="legend" x="{x+24}" y="{y}">{svg_escape(display_name(version))}</text>')

    parts.append('</svg>')
    svg_path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=DEFAULT_INPUT, help="Input benchmark_results.csv path")
    parser.add_argument("--svg", type=Path, default=DEFAULT_OUTPUT, help="Output SVG path")
    parser.add_argument("--include-failed", action="store_true", help="Include non-PASS rows if they have non-negative timing values")
    parser.add_argument("--title", default="RTL Benchmark Execution Time")
    parser.add_argument("--metric", default="ROI", help="Metric label shown on the y-axis; values come from roi_time_ns")
    args = parser.parse_args()

    try:
        rows = read_benchmark_csv(args.csv, include_failed=args.include_failed)
        write_svg(rows, args.svg, args.title, args.metric)
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))

    print(f"Wrote {args.svg}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
