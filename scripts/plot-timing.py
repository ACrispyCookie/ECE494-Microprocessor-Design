#!/usr/bin/env python3
"""Parse Vivado timing path CSV files and generate timing/path distribution comparisons.

Inputs by default:
  reports/baseline/timing_paths.csv
  reports/no-mul-forwarding/timing_paths.csv

Outputs by default:
  reports/summary/timing_metrics.csv
  reports/summary/path_distribution.csv
  reports/plots/slack_histogram.svg
  reports/plots/datapath_delay_histogram.svg

The script intentionally uses only the Python standard library.
"""

from __future__ import annotations

import argparse
import csv
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

DEFAULT_EXPERIMENTS = ("baseline", "no-mul-forwarding")
COLORS = {"baseline": "#2563eb", "no-mul-forwarding": "#dc2626"}
FALLBACK_COLORS = ["#16a34a", "#9333ea", "#ea580c"]


@dataclass(frozen=True)
class TimingPath:
    experiment: str
    index: int
    slack: float | None
    requirement: float | None
    datapath_delay: float | None
    logic_levels: int | None
    startpoint: str
    endpoint: str
    path_group: str


def parse_float(value: str | None) -> float | None:
    if value is None:
        return None
    value = value.strip()
    if not value or value in {"-", "_"}:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def parse_int(value: str | None) -> int | None:
    number = parse_float(value)
    if number is None:
        return None
    return int(number)


def read_paths(path: Path, experiment: str) -> list[TimingPath]:
    if not path.exists():
        raise FileNotFoundError(f"missing timing path CSV for {experiment}: {path}")
    rows: list[TimingPath] = []
    with path.open(newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(
                TimingPath(
                    experiment=experiment,
                    index=parse_int(row.get("index")) or 0,
                    slack=parse_float(row.get("slack")),
                    requirement=parse_float(row.get("requirement")),
                    datapath_delay=parse_float(row.get("datapath_delay")),
                    logic_levels=parse_int(row.get("logic_levels")),
                    startpoint=row.get("startpoint", ""),
                    endpoint=row.get("endpoint", ""),
                    path_group=row.get("path_group", ""),
                )
            )
    if not rows:
        raise ValueError(f"{path} did not contain any timing paths")
    return rows


def hierarchy_category(pin: str) -> str:
    if not pin:
        return "unknown"
    # Keep the first meaningful hierarchy component for coarse critical-path grouping.
    parts = [p for p in pin.replace("[", "/").split("/") if p]
    if not parts:
        return "unknown"
    if parts[0] in {"zedboard_cv32e40p_wrapper", "U0", "dut"} and len(parts) > 1:
        return parts[1]
    return parts[0]


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


def parse_timing_summary(path: Path) -> dict[str, float | None]:
    """Extract top-level timing numbers from Vivado timing_summary_1000_paths.rpt."""
    result: dict[str, float | None] = {
        "summary_wns": None,
        "clock_period": None,
        "clock_frequency_mhz": None,
        "critical_logic_delay": None,
        "critical_route_delay": None,
    }
    if not path.exists():
        return result
    text = path.read_text(encoding="utf-8", errors="replace")

    m = re.search(r"\n\s*([-+]?\d+(?:\.\d+)?)\s+[-+]?\d+(?:\.\d+)?\s+\d+\s+\d+\s+", text)
    if m:
        result["summary_wns"] = float(m.group(1))

    m = re.search(r"^clk_i\s+\{[^}]+\}\s+(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)", text, re.MULTILINE)
    if m:
        result["clock_period"] = float(m.group(1))
        result["clock_frequency_mhz"] = float(m.group(2))

    m = re.search(
        r"Data Path Delay:\s*([-+]?\d+(?:\.\d+)?)ns\s*\(logic\s*([-+]?\d+(?:\.\d+)?)ns.*?route\s*([-+]?\d+(?:\.\d+)?)ns",
        text,
        re.DOTALL,
    )
    if m:
        result["critical_logic_delay"] = float(m.group(2))
        result["critical_route_delay"] = float(m.group(3))
    return result


def metric_rows(paths_by_exp: dict[str, list[TimingPath]], reports_dir: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for exp, paths in paths_by_exp.items():
        valid_slack = [p for p in paths if p.slack is not None]
        crit = min(valid_slack, key=lambda p: p.slack if p.slack is not None else float("inf")) if valid_slack else paths[0]
        summary = parse_timing_summary(reports_dir / exp / "timing_summary_1000_paths.rpt")
        metadata = parse_metadata(reports_dir / exp / "metadata.txt")
        wns = summary["summary_wns"] if summary["summary_wns"] is not None else crit.slack
        clock_period = summary["clock_period"]
        clock_freq = summary["clock_frequency_mhz"]
        requirement = crit.requirement
        fmax_mhz = None
        if clock_period is not None and wns is not None:
            achieved_period = clock_period - wns
            if achieved_period > 0:
                fmax_mhz = 1000.0 / achieved_period
        elif requirement is not None and wns is not None and requirement > 0:
            achieved_period = requirement - wns
            if achieved_period > 0:
                fmax_mhz = 1000.0 / achieved_period
        rows.append(
            {
                "experiment": exp,
                "report_stage": metadata.get("report_stage", ""),
                "num_paths": str(len(paths)),
                "wns_ns": "" if wns is None else f"{wns:.3f}",
                "critical_requirement_ns": "" if requirement is None else f"{requirement:.3f}",
                "clock_period_ns": "" if clock_period is None else f"{clock_period:.3f}",
                "clock_frequency_mhz": "" if clock_freq is None else f"{clock_freq:.3f}",
                "estimated_fmax_mhz_from_wns": "" if fmax_mhz is None else f"{fmax_mhz:.3f}",
                "critical_datapath_delay_ns": "" if crit.datapath_delay is None else f"{crit.datapath_delay:.3f}",
                "critical_logic_delay_ns": "" if summary["critical_logic_delay"] is None else f"{summary['critical_logic_delay']:.3f}",
                "critical_route_delay_ns": "" if summary["critical_route_delay"] is None else f"{summary['critical_route_delay']:.3f}",
                "critical_logic_levels": "" if crit.logic_levels is None else str(crit.logic_levels),
                "critical_startpoint": crit.startpoint,
                "critical_endpoint": crit.endpoint,
                "critical_path_group": crit.path_group,
                "critical_start_hierarchy": hierarchy_category(crit.startpoint),
                "critical_end_hierarchy": hierarchy_category(crit.endpoint),
            }
        )
    return rows


def write_metrics(rows: list[dict[str, str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "experiment",
        "report_stage",
        "num_paths",
        "wns_ns",
        "critical_requirement_ns",
        "clock_period_ns",
        "clock_frequency_mhz",
        "estimated_fmax_mhz_from_wns",
        "critical_datapath_delay_ns",
        "critical_logic_delay_ns",
        "critical_route_delay_ns",
        "critical_logic_levels",
        "critical_startpoint",
        "critical_endpoint",
        "critical_path_group",
        "critical_start_hierarchy",
        "critical_end_hierarchy",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def histogram(values: list[float], bins: int = 20) -> tuple[list[tuple[float, float, int]], float, float]:
    if not values:
        return [], 0.0, 1.0
    lo = min(values)
    hi = max(values)
    if math.isclose(lo, hi):
        lo -= 0.5
        hi += 0.5
    width = (hi - lo) / bins
    counts = [0 for _ in range(bins)]
    for value in values:
        idx = min(bins - 1, max(0, int((value - lo) / width)))
        counts[idx] += 1
    return [(lo + i * width, lo + (i + 1) * width, counts[i]) for i in range(bins)], lo, hi


def write_distribution_csv(paths_by_exp: dict[str, list[TimingPath]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["experiment", "metric", "bin_start", "bin_end", "count"])
        for exp, paths in paths_by_exp.items():
            for metric, getter in [
                ("slack", lambda p: p.slack),
                ("datapath_delay", lambda p: p.datapath_delay),
            ]:
                values = [v for p in paths if (v := getter(p)) is not None]
                for start, end, count in histogram(values)[0]:
                    writer.writerow([exp, metric, f"{start:.3f}", f"{end:.3f}", count])
        writer.writerow([])
        writer.writerow(["experiment", "category", "count"])
        for exp, paths in paths_by_exp.items():
            crit = sorted([p for p in paths if p.slack is not None], key=lambda p: p.slack if p.slack is not None else float("inf"))[:100]
            counts = Counter(hierarchy_category(p.endpoint) for p in crit)
            for category, count in counts.most_common():
                writer.writerow([exp, category, count])


def svg_escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def write_hist_svg(paths_by_exp: dict[str, list[TimingPath]], metric: str, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    getter = (lambda p: p.slack) if metric == "slack" else (lambda p: p.datapath_delay)
    title = "Slack Histogram" if metric == "slack" else "Datapath Delay Histogram"
    x_label = "Slack (ns)" if metric == "slack" else "Datapath delay (ns)"

    experiments = list(paths_by_exp)
    all_values = [v for paths in paths_by_exp.values() for p in paths if (v := getter(p)) is not None]
    bins, lo, hi = histogram(all_values, bins=24)
    bin_edges = [(start, end) for start, end, _count in bins]
    counts_by_exp: dict[str, list[int]] = {}
    max_count = 1
    for exp, paths in paths_by_exp.items():
        values = [v for p in paths if (v := getter(p)) is not None]
        exp_bins, _lo, _hi = histogram(values, bins=24)
        # Re-bin on the shared global range.
        width = (hi - lo) / 24 if hi != lo else 1.0
        counts = [0] * 24
        for value in values:
            idx = min(23, max(0, int((value - lo) / width)))
            counts[idx] += 1
        counts_by_exp[exp] = counts
        max_count = max(max_count, max(counts) if counts else 0)

    width_svg, height_svg = 1100, 620
    ml, mr, mt, mb = 90, 40, 85, 105
    plot_w = width_svg - ml - mr
    plot_h = height_svg - mt - mb
    group_w = plot_w / 24
    bar_gap = 2
    bar_w = max(5, (group_w - 8) / max(1, len(experiments)) - bar_gap)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width_svg}" height="{height_svg}" viewBox="0 0 {width_svg} {height_svg}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<style>text{font-family:Inter,Arial,sans-serif;fill:#111827}.title{font-size:28px;font-weight:700}.subtitle{font-size:14px;fill:#4b5563}.axis{font-size:13px;fill:#374151}.tick{font-size:11px;fill:#6b7280}.grid{stroke:#e5e7eb}.axisline{stroke:#374151;stroke-width:1.5}.legend{font-size:14px}</style>',
        f'<text class="title" x="{width_svg/2}" y="38" text-anchor="middle">{title}</text>',
        f'<text class="subtitle" x="{width_svg/2}" y="62" text-anchor="middle">Parsed from reports/*/timing_paths.csv</text>',
    ]
    for i in range(6):
        tick = max_count * i / 5
        y = mt + plot_h - (tick / max_count) * plot_h
        parts.append(f'<line class="grid" x1="{ml}" y1="{y:.1f}" x2="{width_svg-mr}" y2="{y:.1f}"/>')
        parts.append(f'<text class="tick" x="{ml-8}" y="{y+4:.1f}" text-anchor="end">{tick:.0f}</text>')
    parts.append(f'<line class="axisline" x1="{ml}" y1="{mt}" x2="{ml}" y2="{mt+plot_h}"/>')
    parts.append(f'<line class="axisline" x1="{ml}" y1="{mt+plot_h}" x2="{width_svg-mr}" y2="{mt+plot_h}"/>')
    parts.append(f'<text class="axis" x="22" y="{mt+plot_h/2}" transform="rotate(-90 22 {mt+plot_h/2})" text-anchor="middle">Path count</text>')
    parts.append(f'<text class="axis" x="{ml+plot_w/2}" y="{height_svg-25}" text-anchor="middle">{x_label}</text>')

    for i, (start, end) in enumerate(bin_edges):
        gx = ml + i * group_w
        if i % 3 == 0:
            parts.append(f'<text class="tick" x="{gx+group_w/2:.1f}" y="{mt+plot_h+22}" text-anchor="middle">{start:.2f}</text>')
        for j, exp in enumerate(experiments):
            count = counts_by_exp[exp][i]
            h = (count / max_count) * plot_h if max_count else 0
            x = gx + 4 + j * (bar_w + bar_gap)
            y = mt + plot_h - h
            color = COLORS.get(exp, FALLBACK_COLORS[j % len(FALLBACK_COLORS)])
            parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" fill="{color}" rx="1"/>')

    lx, ly = ml, height_svg - 55
    for j, exp in enumerate(experiments):
        x = lx + j * 250
        color = COLORS.get(exp, FALLBACK_COLORS[j % len(FALLBACK_COLORS)])
        parts.append(f'<rect x="{x}" y="{ly-13}" width="16" height="16" fill="{color}" rx="2"/>')
        parts.append(f'<text class="legend" x="{x+24}" y="{ly}">{svg_escape(exp)}</text>')

    parts.append('</svg>')
    output.write_text("\n".join(parts) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports-dir", type=Path, default=Path("reports"))
    parser.add_argument("--experiments", nargs="+", default=list(DEFAULT_EXPERIMENTS))
    parser.add_argument("--metrics-csv", type=Path, default=Path("reports/summary/timing_metrics.csv"))
    parser.add_argument("--distribution-csv", type=Path, default=Path("reports/summary/path_distribution.csv"))
    parser.add_argument("--slack-svg", type=Path, default=Path("reports/plots/slack_histogram.svg"))
    parser.add_argument("--datapath-svg", type=Path, default=Path("reports/plots/datapath_delay_histogram.svg"))
    args = parser.parse_args()

    try:
        paths_by_exp = {
            exp: read_paths(args.reports_dir / exp / "timing_paths.csv", exp)
            for exp in args.experiments
        }
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))

    write_metrics(metric_rows(paths_by_exp, args.reports_dir), args.metrics_csv)
    write_distribution_csv(paths_by_exp, args.distribution_csv)
    write_hist_svg(paths_by_exp, "slack", args.slack_svg)
    write_hist_svg(paths_by_exp, "datapath_delay", args.datapath_svg)
    print(f"Wrote {args.metrics_csv}")
    print(f"Wrote {args.distribution_csv}")
    print(f"Wrote {args.slack_svg}")
    print(f"Wrote {args.datapath_svg}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
