#!/usr/bin/env python3
"""Parse Vivado utilization reports and generate reproducible comparison plots.

Inputs by default:
  reports/baseline/utilization.rpt
  reports/no-mul-forwarding/utilization.rpt
  reports/no-alu-forwarding/utilization.rpt
  reports/no-alu-mul-forwarding/utilization.rpt

Outputs by default:
  reports/summary/utilization_compare.csv
  reports/plots/utilization_compare.svg

The plotting code intentionally uses only the Python standard library so this
coursework repository does not need matplotlib/pandas just to reproduce the
resource comparison plot.
"""

from __future__ import annotations

import argparse
import csv
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

DEFAULT_EXPERIMENTS = ("baseline", "no-mul-forwarding", "no-alu-forwarding", "no-alu-mul-forwarding")
RESOURCE_LABELS = {
    "Slice LUTs": "LUTs",
    "Slice Registers": "FFs/Regs",
    "DSPs": "DSPs",
    "Block RAM Tile": "BRAM Tiles",
}
RESOURCE_ORDER = ("Slice LUTs", "Slice Registers", "DSPs", "Block RAM Tile")
DISPLAY_NAMES = {
    "baseline": "Baseline",
    "no-mul-forwarding": "No MUL fwd",
    "no-alu-forwarding": "No ALU fwd",
    "no-alu-mul-forwarding": "No ALU+MUL fwd",
}


@dataclass(frozen=True)
class UtilRow:
    experiment: str
    report_stage: str
    resource: str
    label: str
    used: float
    available: float | None
    util_percent: float | None


def parse_number(value: str) -> float | None:
    value = value.strip().replace(",", "")
    if not value or value in {"-", "_"}:
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


def parse_utilization_report(path: Path, experiment: str) -> list[UtilRow]:
    if not path.exists():
        raise FileNotFoundError(f"missing utilization report for {experiment}: {path}")

    metadata = parse_metadata(path.parent / "metadata.txt")
    report_stage = metadata.get("report_stage", "")
    found: dict[str, UtilRow] = {}
    for line in path.read_text(errors="replace").splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 6:
            continue
        site_type, used, _fixed, _prohibited, available, util_pct = cells[:6]
        site_type = re.sub(r"\s+", " ", site_type)
        # Vivado annotates some summary row labels with a trailing footnote
        # marker, e.g. "Slice LUTs*". Normalize those back to the resource key.
        site_type = re.sub(r"\*+$", "", site_type).strip()
        if site_type not in RESOURCE_LABELS:
            continue
        used_num = parse_number(used)
        if used_num is None:
            continue
        found[site_type] = UtilRow(
            experiment=experiment,
            report_stage=report_stage,
            resource=site_type,
            label=RESOURCE_LABELS[site_type],
            used=used_num,
            available=parse_number(available),
            util_percent=parse_number(util_pct),
        )

    missing = [resource for resource in RESOURCE_ORDER if resource not in found]
    if missing:
        raise ValueError(f"{path} did not contain expected resources: {', '.join(missing)}")
    return [found[resource] for resource in RESOURCE_ORDER]


def write_csv(rows: Iterable[UtilRow], csv_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["experiment", "report_stage", "resource", "label", "used", "available", "util_percent"])
        for row in rows:
            writer.writerow([
                row.experiment,
                row.report_stage,
                row.resource,
                row.label,
                f"{row.used:g}",
                "" if row.available is None else f"{row.available:g}",
                "" if row.util_percent is None else f"{row.util_percent:g}",
            ])


def fmt_num(value: float) -> str:
    return str(int(value)) if value.is_integer() else f"{value:g}"


def fmt_percent(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".") + "%"


def utilization_percent(row: UtilRow) -> float:
    if row.util_percent is not None:
        return row.util_percent
    if row.available and row.available > 0:
        return 100.0 * row.used / row.available
    raise ValueError(f"missing utilization percentage/available count for {row.experiment} {row.resource}")


def svg_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def display_name(experiment: str) -> str:
    return DISPLAY_NAMES.get(experiment, experiment)


def write_svg(rows: list[UtilRow], svg_path: Path) -> None:
    svg_path.parent.mkdir(parents=True, exist_ok=True)

    experiments = list(dict.fromkeys(row.experiment for row in rows))
    resources = [RESOURCE_LABELS[resource] for resource in RESOURCE_ORDER]
    by_key = {(row.experiment, row.label): row for row in rows}

    width = 1180
    height = 680
    margin_left = 125
    margin_right = 65
    margin_top = 95
    margin_bottom = 125
    plot_w = width - margin_left - margin_right
    plot_h = height - margin_top - margin_bottom

    utilization_values = [utilization_percent(row) for row in rows]
    max_util = max(utilization_values) if utilization_values else 1.0
    max_util = max(max_util, 1.0)
    # Keep slide ticks clean: this design is below 10%, so a fixed 0-10% scale
    # makes small differences visible without misleading autoscaling.
    y_max = max(10.0, math.ceil(max_util * 1.15))

    colors = {"baseline": "#2563eb", "no-mul-forwarding": "#dc2626", "no-alu-forwarding": "#16a34a", "no-alu-mul-forwarding": "#9333ea"}
    fallback_colors = ["#16a34a", "#9333ea", "#ea580c"]

    group_w = plot_w / len(resources)
    bar_gap = 12
    bar_w = min(90, (group_w - 50) / max(len(experiments), 1) - bar_gap)
    if bar_w < 18:
        bar_w = 18

    def x_for(i: int, j: int) -> float:
        group_x = margin_left + i * group_w
        bars_total = len(experiments) * bar_w + (len(experiments) - 1) * bar_gap
        return group_x + (group_w - bars_total) / 2 + j * (bar_w + bar_gap)

    def y_for(value: float) -> float:
        return margin_top + plot_h - (value / y_max) * plot_h

    tick_count = 5
    ticks = [y_max * i / tick_count for i in range(tick_count + 1)]

    parts: list[str] = []
    parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">')
    parts.append('<rect width="100%" height="100%" fill="#ffffff"/>')
    parts.append('<style>text{font-family:Inter,Arial,sans-serif;fill:#111827}.title{font-size:30px;font-weight:700}.subtitle{font-size:15px;fill:#4b5563}.axis{font-size:15px;font-weight:600;fill:#374151}.tick{font-size:13px;fill:#6b7280}.label{font-size:13px;fill:#111827}.legend{font-size:14px}.grid{stroke:#e5e7eb;stroke-width:1}.axisline{stroke:#374151;stroke-width:1.5}</style>')
    parts.append(f'<text class="title" x="{width/2}" y="38" text-anchor="middle">FPGA Resource Utilization</text>')
    parts.append(f'<text class="subtitle" x="{width/2}" y="64" text-anchor="middle">Post-implementation utilization on Zynq-7020</text>')

    # Grid and y-axis.
    for tick in ticks:
        y = y_for(tick)
        parts.append(f'<line class="grid" x1="{margin_left}" y1="{y:.1f}" x2="{width-margin_right}" y2="{y:.1f}"/>')
        parts.append(f'<text class="tick" x="{margin_left-10}" y="{y+4:.1f}" text-anchor="end">{fmt_percent(tick)}</text>')
    parts.append(f'<line class="axisline" x1="{margin_left}" y1="{margin_top}" x2="{margin_left}" y2="{margin_top+plot_h}"/>')
    parts.append(f'<line class="axisline" x1="{margin_left}" y1="{margin_top+plot_h}" x2="{width-margin_right}" y2="{margin_top+plot_h}"/>')
    parts.append(f'<text class="axis" x="30" y="{margin_top+plot_h/2}" text-anchor="middle" transform="rotate(-90 30 {margin_top+plot_h/2})">FPGA utilization (% of Zynq-7020)</text>')
    parts.append(f'<text class="axis" x="{margin_left+plot_w/2}" y="{height-28}" text-anchor="middle">Vivado report_utilization resource type</text>')

    # Bars.
    for i, resource in enumerate(resources):
        center_x = margin_left + i * group_w + group_w / 2
        parts.append(f'<text class="axis" x="{center_x:.1f}" y="{margin_top+plot_h+35}" text-anchor="middle">{svg_escape(resource)}</text>')
        for j, experiment in enumerate(experiments):
            row = by_key.get((experiment, resource))
            if row is None:
                continue
            x = x_for(i, j)
            util_pct = utilization_percent(row)
            y = y_for(util_pct)
            h = margin_top + plot_h - y
            color = colors.get(experiment, fallback_colors[j % len(fallback_colors)])
            parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" fill="{color}" rx="3"/>')
            parts.append(f'<text class="label" x="{x+bar_w/2:.1f}" y="{y-7:.1f}" text-anchor="middle">{fmt_percent(util_pct)}</text>')

    # Legend.
    legend_x = margin_left
    legend_y = height - 45
    for j, experiment in enumerate(experiments):
        color = colors.get(experiment, fallback_colors[j % len(fallback_colors)])
        x = legend_x + j * 230
        parts.append(f'<rect x="{x}" y="{legend_y-13}" width="16" height="16" fill="{color}" rx="2"/>')
        parts.append(f'<text class="legend" x="{x+24}" y="{legend_y}">{svg_escape(display_name(experiment))}</text>')

    parts.append('</svg>')
    svg_path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports-dir", type=Path, default=Path("reports"))
    parser.add_argument("--experiments", nargs="+", default=list(DEFAULT_EXPERIMENTS))
    parser.add_argument("--csv", type=Path, default=Path("reports/summary/utilization_compare.csv"))
    parser.add_argument("--svg", type=Path, default=Path("reports/plots/utilization_compare.svg"))
    args = parser.parse_args()

    rows: list[UtilRow] = []
    try:
        for experiment in args.experiments:
            rows.extend(parse_utilization_report(args.reports_dir / experiment / "utilization.rpt", experiment))
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))

    write_csv(rows, args.csv)
    write_svg(rows, args.svg)

    print(f"Wrote {args.csv}")
    print(f"Wrote {args.svg}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
