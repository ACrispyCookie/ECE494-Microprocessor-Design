#!/usr/bin/env python3
"""Generate a presentation-ready CSV and SVG table from Vivado summary CSVs.

Inputs by default:
  reports/summary/timing_metrics.csv
  reports/summary/utilization_compare.csv

Outputs by default:
  reports/summary/presentation_comparison.csv
  reports/plots/presentation_comparison_table.svg

The output table is intended for slides: it puts the baseline, modified
version, delta, and interpretation in one compact visual.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path

DEFAULT_BASELINE = "baseline"
DEFAULT_MODIFIED = "no-mul-forwarding"
RESOURCE_LABELS = {
    "Slice LUTs": "LUTs",
    "Slice Registers": "FFs / Regs",
    "DSPs": "DSPs",
    "Block RAM Tile": "BRAM Tiles",
}
RESOURCE_ORDER = ("Slice LUTs", "Slice Registers", "DSPs", "Block RAM Tile")


@dataclass(frozen=True)
class PresentationRow:
    category: str
    metric: str
    unit: str
    baseline: float
    modified: float
    delta: float
    delta_percent: float | None
    direction: str
    interpretation: str


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"missing input CSV: {path}")
    with path.open(newline="", encoding="utf-8", errors="replace") as f:
        return list(csv.DictReader(f))


def as_float(row: dict[str, str], key: str) -> float:
    value = row.get(key, "").strip()
    if not value:
        raise ValueError(f"missing value for {key} in row {row}")
    return float(value)


def fmt_number(value: float, unit: str = "", signed: bool = False) -> str:
    sign = "+" if signed and value > 0 else ""
    abs_value = abs(value)
    if unit in {"MHz", "ns", "pp"}:
        return f"{sign}{value:.3f}".rstrip("0").rstrip(".")
    if abs_value >= 100 or float(value).is_integer():
        return f"{sign}{value:.0f}"
    return f"{sign}{value:.2f}".rstrip("0").rstrip(".")


def fmt_cell(value: float, unit: str) -> str:
    return f"{fmt_number(value, unit)} {unit}".strip()


def fmt_delta(value: float, unit: str) -> str:
    return f"{fmt_number(value, unit, signed=True)} {unit}".strip()


def percentage_delta(baseline: float, modified: float) -> float | None:
    if baseline == 0:
        return None
    return 100.0 * (modified - baseline) / baseline


def make_row(
    category: str,
    metric: str,
    unit: str,
    baseline: float,
    modified: float,
    higher_is_better: bool,
    interpretation: str,
) -> PresentationRow:
    delta = modified - baseline
    delta_pct = percentage_delta(baseline, modified)
    if abs(delta) < 1e-12:
        direction = "same"
    elif (delta > 0 and higher_is_better) or (delta < 0 and not higher_is_better):
        direction = "better"
    else:
        direction = "cost"
    return PresentationRow(category, metric, unit, baseline, modified, delta, delta_pct, direction, interpretation)


def build_rows(
    timing_rows: list[dict[str, str]],
    util_rows: list[dict[str, str]],
    baseline_name: str,
    modified_name: str,
) -> list[PresentationRow]:
    timing = {row["experiment"]: row for row in timing_rows}
    if baseline_name not in timing or modified_name not in timing:
        raise ValueError(f"timing CSV must contain {baseline_name} and {modified_name}")

    base_t = timing[baseline_name]
    mod_t = timing[modified_name]
    rows: list[PresentationRow] = [
        make_row(
            "Frequency",
            "Target clock frequency",
            "MHz",
            as_float(base_t, "clock_frequency_mhz"),
            as_float(mod_t, "clock_frequency_mhz"),
            higher_is_better=True,
            interpretation="higher target frequency",
        ),
        make_row(
            "Frequency",
            "Estimated Fmax from WNS",
            "MHz",
            as_float(base_t, "estimated_fmax_mhz_from_wns"),
            as_float(mod_t, "estimated_fmax_mhz_from_wns"),
            higher_is_better=True,
            interpretation="higher estimated Fmax",
        ),
        make_row(
            "Timing",
            "Worst negative slack (WNS)",
            "ns",
            as_float(base_t, "wns_ns"),
            as_float(mod_t, "wns_ns"),
            higher_is_better=True,
            interpretation="more timing margin",
        ),
        make_row(
            "Timing",
            "Critical datapath delay",
            "ns",
            as_float(base_t, "critical_datapath_delay_ns"),
            as_float(mod_t, "critical_datapath_delay_ns"),
            higher_is_better=False,
            interpretation="shorter critical path",
        ),
    ]

    util_by_key = {(row["experiment"], row["resource"]): row for row in util_rows}
    for resource in RESOURCE_ORDER:
        base_u = util_by_key.get((baseline_name, resource))
        mod_u = util_by_key.get((modified_name, resource))
        if base_u is None or mod_u is None:
            raise ValueError(f"utilization CSV missing resource {resource} for one of the experiments")
        label = RESOURCE_LABELS[resource]
        rows.append(
            make_row(
                "Utilization",
                f"{label} used",
                "count",
                as_float(base_u, "used"),
                as_float(mod_u, "used"),
                higher_is_better=False,
                interpretation="lower resource cost is better",
            )
        )
        rows.append(
            make_row(
                "Utilization",
                f"{label} utilization",
                "%",
                as_float(base_u, "util_percent"),
                as_float(mod_u, "util_percent"),
                higher_is_better=False,
                interpretation="lower FPGA occupancy is better",
            )
        )
    return rows


def write_summary_csv(rows: list[PresentationRow], path: Path, baseline_name: str, modified_name: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "category",
        "metric",
        "unit",
        baseline_name,
        modified_name,
        "delta",
        "delta_percent",
        "direction",
        "interpretation",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "category": row.category,
                    "metric": row.metric,
                    "unit": row.unit,
                    baseline_name: f"{row.baseline:.6g}",
                    modified_name: f"{row.modified:.6g}",
                    "delta": f"{row.delta:.6g}",
                    "delta_percent": "" if row.delta_percent is None else f"{row.delta_percent:.6g}",
                    "direction": row.direction,
                    "interpretation": row.interpretation,
                }
            )


def svg_escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def direction_badge(row: PresentationRow) -> tuple[str, str, str]:
    if row.direction == "better":
        return "Improved", "#dcfce7", "#166534"
    if row.direction == "cost":
        return "Cost", "#fef3c7", "#92400e"
    return "Same", "#e5e7eb", "#374151"


def write_table_svg(rows: list[PresentationRow], path: Path, baseline_name: str, modified_name: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    width = 1500
    row_h = 46
    header_h = 104
    footer_h = 42
    height = header_h + row_h * (len(rows) + 1) + footer_h
    x = [40, 190, 560, 760, 970, 1160, 1320]
    col_w = [140, 360, 190, 200, 180, 150, 140]

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<style>text{font-family:Inter,Arial,sans-serif;fill:#111827}.title{font-size:30px;font-weight:800}.subtitle{font-size:15px;fill:#4b5563}.head{font-size:14px;font-weight:700;fill:#374151}.cell{font-size:14px}.metric{font-size:14px;font-weight:650}.small{font-size:12px;fill:#6b7280}.num{font-size:14px;font-variant-numeric:tabular-nums}.badge{font-size:12px;font-weight:700}.grid{stroke:#e5e7eb;stroke-width:1}.strong{font-weight:800}</style>',
        f'<text class="title" x="{width/2}" y="38" text-anchor="middle">Post-Implementation Comparison Summary</text>',
        f'<text class="subtitle" x="{width/2}" y="64" text-anchor="middle">{svg_escape(baseline_name)} vs {svg_escape(modified_name)} — frequency, timing margin, utilization, and deltas</text>',
    ]

    table_y = 86
    headers = ["Category", "Metric", baseline_name, modified_name, "Delta", "Meaning", "Result"]
    parts.append(f'<rect x="30" y="{table_y}" width="{width-60}" height="{row_h}" fill="#f8fafc" rx="8"/>')
    for i, header in enumerate(headers):
        parts.append(f'<text class="head" x="{x[i]}" y="{table_y+29}">{svg_escape(header)}</text>')
    parts.append(f'<line class="grid" x1="30" y1="{table_y+row_h}" x2="{width-30}" y2="{table_y+row_h}"/>')

    y = table_y + row_h
    prev_category = None
    for idx, row in enumerate(rows):
        y0 = y + idx * row_h
        fill = "#ffffff" if idx % 2 == 0 else "#fbfdff"
        parts.append(f'<rect x="30" y="{y0}" width="{width-60}" height="{row_h}" fill="{fill}"/>')
        parts.append(f'<line class="grid" x1="30" y1="{y0+row_h}" x2="{width-30}" y2="{y0+row_h}"/>')
        if row.category != prev_category:
            parts.append(f'<text class="cell strong" x="{x[0]}" y="{y0+29}">{svg_escape(row.category)}</text>')
            prev_category = row.category
        parts.append(f'<text class="metric" x="{x[1]}" y="{y0+29}">{svg_escape(row.metric)}</text>')
        parts.append(f'<text class="num" x="{x[2]}" y="{y0+29}">{svg_escape(fmt_cell(row.baseline, row.unit))}</text>')
        parts.append(f'<text class="num strong" x="{x[3]}" y="{y0+29}">{svg_escape(fmt_cell(row.modified, row.unit))}</text>')
        delta_text = fmt_delta(row.delta, "pp" if row.unit == "%" else row.unit)
        if row.delta_percent is not None and row.unit not in {"%", "pp"}:
            delta_text += f" ({row.delta_percent:+.1f}%)"
        delta_color = "#166534" if row.direction == "better" else "#92400e" if row.direction == "cost" else "#374151"
        parts.append(f'<text class="num strong" x="{x[4]}" y="{y0+29}" fill="{delta_color}">{svg_escape(delta_text)}</text>')
        parts.append(f'<text class="cell" x="{x[5]}" y="{y0+29}">{svg_escape(row.interpretation)}</text>')
        label, bg, fg = direction_badge(row)
        parts.append(f'<rect x="{x[6]}" y="{y0+10}" width="92" height="26" rx="13" fill="{bg}"/>')
        parts.append(f'<text class="badge" x="{x[6]+46}" y="{y0+28}" text-anchor="middle" fill="{fg}">{label}</text>')

    # Vertical separators.
    for sep in x[1:]:
        parts.append(f'<line class="grid" x1="{sep-12}" y1="{table_y}" x2="{sep-12}" y2="{table_y+row_h*(len(rows)+1)}"/>')

    footer_y = table_y + row_h * (len(rows) + 1) + 28
    parts.append(f'<text class="small" x="40" y="{footer_y}">Generated from reports/summary/timing_metrics.csv and utilization_compare.csv. Positive timing/frequency deltas are improvements; positive utilization deltas are resource cost.</text>')
    parts.append('</svg>')
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timing-csv", type=Path, default=Path("reports/summary/timing_metrics.csv"))
    parser.add_argument("--utilization-csv", type=Path, default=Path("reports/summary/utilization_compare.csv"))
    parser.add_argument("--csv", type=Path, default=Path("reports/summary/presentation_comparison.csv"))
    parser.add_argument("--svg", type=Path, default=Path("reports/plots/presentation_comparison_table.svg"))
    parser.add_argument("--baseline", default=DEFAULT_BASELINE)
    parser.add_argument("--modified", default=DEFAULT_MODIFIED)
    args = parser.parse_args()

    try:
        rows = build_rows(read_csv(args.timing_csv), read_csv(args.utilization_csv), args.baseline, args.modified)
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))

    write_summary_csv(rows, args.csv, args.baseline, args.modified)
    write_table_svg(rows, args.svg, args.baseline, args.modified)
    print(f"Wrote {args.csv}")
    print(f"Wrote {args.svg}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
