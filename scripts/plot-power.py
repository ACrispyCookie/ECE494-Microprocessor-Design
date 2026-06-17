#!/usr/bin/env python3
"""Parse Vivado power reports and generate CSV/SVG power comparisons.

Inputs by default:
  reports/baseline/power.rpt
  reports/no-mul-forwarding/power.rpt

Outputs by default:
  reports/<experiment>/power_metrics.csv
  reports/summary/power_metrics.csv
  reports/plots/power_compare.svg

The parser is intentionally tolerant of Vivado report_power formatting. It
extracts the common total/dynamic/static rows from the Power Summary section and
also records power-by-category rows when they are present in the report table.
The plotting code uses only the Python standard library.
"""

from __future__ import annotations

import argparse
import csv
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

DEFAULT_EXPERIMENTS = ("baseline", "no-mul-forwarding")
COLORS = {"baseline": "#2563eb", "no-mul-forwarding": "#dc2626"}
FALLBACK_COLORS = ["#16a34a", "#9333ea", "#9333ea", "#ea580c"]
SUMMARY_ORDER = (
    "total_on_chip_power_w",
    "dynamic_power_w",
    "device_static_power_w",
)
SUMMARY_LABELS = {
    "total_on_chip_power_w": "Total On-Chip",
    "dynamic_power_w": "Dynamic",
    "device_static_power_w": "Static",
}


@dataclass(frozen=True)
class PowerRow:
    experiment: str
    report_stage: str
    metric: str
    label: str
    value_w: float
    percent: float | None = None


def parse_float(value: str | None) -> float | None:
    if value is None:
        return None
    value = value.strip().replace(",", "")
    value = re.sub(r"[^0-9eE+\-.]", "", value)
    if not value or value in {"-", ".", "+", "_"}:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def parse_metadata(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    metadata: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        metadata[key.strip()] = value.strip()
    return metadata


def normalize_label(label: str) -> str:
    label = re.sub(r"\([^)]*\)", "", label)
    label = re.sub(r"\[[^]]*\]", "", label)
    label = re.sub(r"\s+", " ", label.replace("*", "")).strip()
    return label


def metric_key(label: str) -> str:
    key = normalize_label(label).lower()
    key = key.replace("on-chip", "on_chip")
    key = re.sub(r"[^a-z0-9]+", "_", key).strip("_")
    return key


def parse_table_rows(text: str) -> Iterable[list[str]]:
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or stripped.startswith("+-"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) < 2:
            continue
        # Skip table headers/separators.
        joined = " ".join(cells).lower()
        if "name" in joined and "power" in joined and "dynamic" in joined:
            continue
        if all(set(cell) <= {"-", ":", " "} for cell in cells):
            continue
        yield cells


def extract_summary_metric(cells: list[str]) -> tuple[str, str, float] | None:
    """Return (metric, label, watts) for total/dynamic/static summary rows."""
    label = normalize_label(cells[0])
    label_l = label.lower()

    # Typical Vivado rows contain the value in the second column, e.g.
    # | Total On-Chip Power (W) | 0.123 |
    # Some summary tables place dynamic/static in a category table; those are
    # handled separately below.
    value = parse_float(cells[1] if len(cells) > 1 else None)
    if value is None:
        return None

    if "total on-chip power" in label_l or "total on chip power" in label_l:
        return "total_on_chip_power_w", "Total On-Chip", value
    if label_l == "dynamic" or "dynamic power" in label_l:
        return "dynamic_power_w", "Dynamic", value
    if "device static" in label_l or "static power" in label_l:
        return "device_static_power_w", "Static", value
    return None


def extract_category_metric(cells: list[str]) -> PowerRow | None:
    """Parse common report_power category rows.

    Vivado category tables commonly look like:
      | Clocks | 0.010 | 0.000 | 0.010 | 10.0 |
    where the dynamic power is generally the first numeric power column. We keep
    these as category_<name>_dynamic_w metrics. If a percent column is present it
    is recorded too.
    """
    label = normalize_label(cells[0])
    if not label or label.lower() in {"name", "power", "summary"}:
        return None
    if any(token in label.lower() for token in ["total on-chip", "dynamic power", "device static"]):
        return None
    numbers = [parse_float(cell) for cell in cells[1:]]
    numbers = [n for n in numbers if n is not None]
    if not numbers:
        return None
    # Ignore rows that are clearly not component/category rows.
    known = {
        "clocks", "signals", "logic", "bram", "block ram", "dsp", "io",
        "i/o", "static", "device static", "processing system", "ps7", "pl",
        "mmcm", "pll", "gt", "uram", "registers", "nets",
    }
    label_l = label.lower()
    if not any(k in label_l for k in known):
        return None
    value = numbers[0]
    percent = numbers[-1] if len(numbers) >= 2 and 0.0 <= numbers[-1] <= 100.0 else None
    return PowerRow(
        experiment="",
        report_stage="",
        metric=f"category_{metric_key(label)}_dynamic_w",
        label=f"{label} Dynamic",
        value_w=value,
        percent=percent,
    )


def parse_power_report(path: Path, experiment: str) -> list[PowerRow]:
    if not path.exists():
        raise FileNotFoundError(f"missing power report for {experiment}: {path}")
    metadata = parse_metadata(path.parent / "metadata.txt")
    report_stage = metadata.get("report_stage", "")
    text = path.read_text(encoding="utf-8", errors="replace")

    summary: dict[str, PowerRow] = {}
    categories: dict[str, PowerRow] = {}
    for cells in parse_table_rows(text):
        parsed = extract_summary_metric(cells)
        if parsed is not None:
            metric, label, value = parsed
            summary[metric] = PowerRow(experiment, report_stage, metric, label, value)
            continue
        cat = extract_category_metric(cells)
        if cat is not None:
            categories[cat.metric] = PowerRow(
                experiment=experiment,
                report_stage=report_stage,
                metric=cat.metric,
                label=cat.label,
                value_w=cat.value_w,
                percent=cat.percent,
            )

    # Fallback regexes for summary values if the table parser misses them.
    fallback_patterns = {
        "total_on_chip_power_w": (r"Total\s+On-?Chip\s+Power\s*\(?W\)?\s*[:|]?\s*([-+]?\d+(?:\.\d+)?)", "Total On-Chip"),
        "dynamic_power_w": (r"Dynamic\s+(?:Power)?\s*\(?W\)?\s*[:|]?\s*([-+]?\d+(?:\.\d+)?)", "Dynamic"),
        "device_static_power_w": (r"Device\s+Static\s+(?:Power)?\s*\(?W\)?\s*[:|]?\s*([-+]?\d+(?:\.\d+)?)", "Static"),
    }
    for metric, (pattern, label) in fallback_patterns.items():
        if metric in summary:
            continue
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = parse_float(match.group(1))
            if value is not None:
                summary[metric] = PowerRow(experiment, report_stage, metric, label, value)

    if not summary:
        raise ValueError(f"{path} did not contain recognizable Vivado power summary rows")

    ordered = [summary[m] for m in SUMMARY_ORDER if m in summary]
    ordered.extend(row for key, row in sorted(categories.items()) if key not in summary)
    return ordered


def write_csv(rows: list[PowerRow], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["experiment", "report_stage", "metric", "label", "value_w", "percent"])
        for row in rows:
            writer.writerow([
                row.experiment,
                row.report_stage,
                row.metric,
                row.label,
                f"{row.value_w:.6g}",
                "" if row.percent is None else f"{row.percent:.6g}",
            ])


def svg_escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def fmt_w(value: float) -> str:
    if value >= 1.0:
        return f"{value:.3f} W".rstrip("0").rstrip(".")
    return f"{value * 1000.0:.1f} mW".rstrip("0").rstrip(".")


def write_svg(rows: list[PowerRow], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    summary_rows = [row for row in rows if row.metric in SUMMARY_ORDER]
    if not summary_rows:
        raise ValueError("no summary power rows available for plotting")
    experiments = list(dict.fromkeys(row.experiment for row in summary_rows))
    metrics = [metric for metric in SUMMARY_ORDER if any(row.metric == metric for row in summary_rows)]
    by_key = {(row.experiment, row.metric): row for row in summary_rows}

    width, height = 1100, 650
    ml, mr, mt, mb = 110, 55, 90, 120
    plot_w = width - ml - mr
    plot_h = height - mt - mb
    max_value = max((row.value_w for row in summary_rows), default=1.0)
    y_max = max(0.01, max_value * 1.2)
    # Use a clean upper bound in W.
    magnitude = 10 ** math.floor(math.log10(y_max)) if y_max > 0 else 1
    y_max = math.ceil(y_max / magnitude * 5) / 5 * magnitude

    def y_for(value: float) -> float:
        return mt + plot_h - (value / y_max) * plot_h

    group_w = plot_w / len(metrics)
    gap = 14
    bar_w = min(110, (group_w - 55) / max(len(experiments), 1) - gap)
    bar_w = max(20, bar_w)

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<style>text{font-family:Inter,Arial,sans-serif;fill:#111827}.title{font-size:28px;font-weight:700}.subtitle{font-size:14px;fill:#4b5563}.axis{font-size:13px;fill:#374151}.tick{font-size:12px;fill:#6b7280}.label{font-size:12px;fill:#111827}.legend{font-size:14px}.grid{stroke:#e5e7eb;stroke-width:1}.axisline{stroke:#374151;stroke-width:1.5}</style>',
        f'<text class="title" x="{width/2}" y="38" text-anchor="middle">Vivado Power Comparison</text>',
        f'<text class="subtitle" x="{width/2}" y="62" text-anchor="middle">Summary power metrics parsed from reports/*/power.rpt</text>',
    ]

    for i in range(6):
        tick = y_max * i / 5
        y = y_for(tick)
        parts.append(f'<line class="grid" x1="{ml}" y1="{y:.1f}" x2="{width-mr}" y2="{y:.1f}"/>')
        parts.append(f'<text class="tick" x="{ml-10}" y="{y+4:.1f}" text-anchor="end">{tick:.3g}</text>')
    parts.append(f'<line class="axisline" x1="{ml}" y1="{mt}" x2="{ml}" y2="{mt+plot_h}"/>')
    parts.append(f'<line class="axisline" x1="{ml}" y1="{mt+plot_h}" x2="{width-mr}" y2="{mt+plot_h}"/>')
    parts.append(f'<text class="axis" x="30" y="{mt+plot_h/2}" text-anchor="middle" transform="rotate(-90 30 {mt+plot_h/2})">Power (W)</text>')

    for i, metric in enumerate(metrics):
        center = ml + i * group_w + group_w / 2
        parts.append(f'<text class="axis" x="{center:.1f}" y="{mt+plot_h+36}" text-anchor="middle">{svg_escape(SUMMARY_LABELS[metric])}</text>')
        total_w = len(experiments) * bar_w + (len(experiments) - 1) * gap
        for j, exp in enumerate(experiments):
            row = by_key.get((exp, metric))
            if row is None:
                continue
            x = ml + i * group_w + (group_w - total_w) / 2 + j * (bar_w + gap)
            y = y_for(row.value_w)
            h = mt + plot_h - y
            color = COLORS.get(exp, FALLBACK_COLORS[j % len(FALLBACK_COLORS)])
            parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" fill="{color}" rx="3"/>')
            parts.append(f'<text class="label" x="{x+bar_w/2:.1f}" y="{max(y-7, mt-6):.1f}" text-anchor="middle">{svg_escape(fmt_w(row.value_w))}</text>')

    lx, ly = ml, height - 48
    for j, exp in enumerate(experiments):
        x = lx + j * 260
        color = COLORS.get(exp, FALLBACK_COLORS[j % len(FALLBACK_COLORS)])
        parts.append(f'<rect x="{x}" y="{ly-13}" width="16" height="16" fill="{color}" rx="2"/>')
        parts.append(f'<text class="legend" x="{x+24}" y="{ly}">{svg_escape(exp)}</text>')

    parts.append('</svg>')
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports-dir", type=Path, default=Path("reports"))
    parser.add_argument("--experiments", nargs="+", default=list(DEFAULT_EXPERIMENTS))
    parser.add_argument("--summary-csv", type=Path, default=Path("reports/summary/power_metrics.csv"))
    parser.add_argument("--svg", type=Path, default=Path("reports/plots/power_compare.svg"))
    parser.add_argument("--no-svg", action="store_true", help="write CSV outputs only; do not generate the SVG plot")
    args = parser.parse_args()

    all_rows: list[PowerRow] = []
    try:
        for experiment in args.experiments:
            rows = parse_power_report(args.reports_dir / experiment / "power.rpt", experiment)
            all_rows.extend(rows)
            write_csv(rows, args.reports_dir / experiment / "power_metrics.csv")
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))

    write_csv(all_rows, args.summary_csv)
    if not args.no_svg:
        write_svg(all_rows, args.svg)
    print(f"Wrote {args.summary_csv}")
    if not args.no_svg:
        print(f"Wrote {args.svg}")
    for experiment in args.experiments:
        print(f"Wrote {args.reports_dir / experiment / 'power_metrics.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
