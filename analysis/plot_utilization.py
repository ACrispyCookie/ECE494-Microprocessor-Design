#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

import matplotlib.pyplot as plt


RESOURCE_ALIASES = {
    "Slice LUTs": ["Slice LUTs", "CLB LUTs"],
    "Slice Registers": ["Slice Registers", "CLB Registers"],
    "Block RAM Tile": ["Block RAM Tile"],
    "RAMB36/FIFO": ["RAMB36/FIFO", "RAMB36"],
    "RAMB18": ["RAMB18"],
    "DSPs": ["DSPs", "DSP Blocks"],
}


def parse_vivado_utilization(report_path: Path) -> dict[str, dict[str, float]]:
    """
    Parse a Vivado utilization.rpt file.

    Returns:
        {
            "Slice LUTs": {"used": ..., "available": ..., "percent": ...},
            ...
        }
    """

    if not report_path.exists():
        raise FileNotFoundError(f"Report not found: {report_path}")

    parsed: dict[str, dict[str, float]] = {}

    # Typical Vivado utilization row:
    # | Slice LUTs* | 4076 | 0 | 53200 | 7.66 |
    # or:
    # | DSPs        | 5    |   | 220   | 2.27 |
    #
    # We parse table rows by splitting on '|'.
    with report_path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if "|" not in line:
                continue

            fields = [x.strip() for x in line.split("|")]
            fields = [x for x in fields if x]

            if len(fields) < 4:
                continue

            raw_name = fields[0].replace("*", "").strip()

            for canonical_name, aliases in RESOURCE_ALIASES.items():
                if raw_name not in aliases:
                    continue

                numbers = []
                for field in fields[1:]:
                    # Remove annotations and keep numeric-looking values.
                    cleaned = field.replace(",", "")
                    if re.fullmatch(r"-?\d+(\.\d+)?", cleaned):
                        numbers.append(float(cleaned))

                # Vivado rows usually include used, fixed, available, util%.
                # Depending on resource, there may be fewer columns.
                if len(numbers) >= 3:
                    used = numbers[0]
                    available = numbers[-2]
                    percent = numbers[-1]

                    parsed[canonical_name] = {
                        "used": used,
                        "available": available,
                        "percent": percent,
                    }

    return parsed


def write_summary_csv(
    out_csv: Path,
    baseline: dict[str, dict[str, float]],
    modified: dict[str, dict[str, float]],
    baseline_label: str,
    modified_label: str,
) -> None:
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    resources = list(RESOURCE_ALIASES.keys())

    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "resource",
                f"{baseline_label}_used",
                f"{baseline_label}_available",
                f"{baseline_label}_percent",
                f"{modified_label}_used",
                f"{modified_label}_available",
                f"{modified_label}_percent",
                "used_delta",
                "percent_delta",
            ]
        )

        for resource in resources:
            b = baseline.get(resource, {"used": 0.0, "available": 0.0, "percent": 0.0})
            m = modified.get(resource, {"used": 0.0, "available": 0.0, "percent": 0.0})

            writer.writerow(
                [
                    resource,
                    b["used"],
                    b["available"],
                    b["percent"],
                    m["used"],
                    m["available"],
                    m["percent"],
                    m["used"] - b["used"],
                    m["percent"] - b["percent"],
                ]
            )


def plot_utilization_percent(
    out_png: Path,
    out_pdf: Path,
    baseline: dict[str, dict[str, float]],
    modified: dict[str, dict[str, float]],
    baseline_label: str,
    modified_label: str,
) -> None:
    resources = list(RESOURCE_ALIASES.keys())

    baseline_values = [baseline.get(r, {"percent": 0.0})["percent"] for r in resources]
    modified_values = [modified.get(r, {"percent": 0.0})["percent"] for r in resources]

    y = list(range(len(resources)))
    bar_height = 0.36

    fig, ax = plt.subplots(figsize=(10, 5.5))

    ax.barh(
        [pos - bar_height / 2 for pos in y],
        baseline_values,
        height=bar_height,
        label=baseline_label,
    )

    ax.barh(
        [pos + bar_height / 2 for pos in y],
        modified_values,
        height=bar_height,
        label=modified_label,
    )

    ax.set_yticks(y)
    ax.set_yticklabels(resources)
    ax.set_xlabel("Utilization (%)")
    ax.set_title("Vivado Resource Utilization Comparison")
    ax.grid(axis="x", linestyle="--", linewidth=0.5)
    ax.legend()

    # Add value labels at the end of each bar.
    for pos, value in zip([p - bar_height / 2 for p in y], baseline_values):
        ax.text(value, pos, f" {value:.2f}%", va="center", fontsize=8)

    for pos, value in zip([p + bar_height / 2 for p in y], modified_values):
        ax.text(value, pos, f" {value:.2f}%", va="center", fontsize=8)

    max_value = max(baseline_values + modified_values + [1.0])
    ax.set_xlim(0, max_value * 1.20)

    fig.tight_layout()

    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=200)
    fig.savefig(out_pdf)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare Vivado utilization reports and generate a bar chart."
    )

    parser.add_argument(
        "--baseline",
        type=Path,
        default=Path("reports/baseline/utilization.rpt"),
        help="Baseline utilization.rpt path.",
    )

    parser.add_argument(
        "--modified",
        type=Path,
        default=Path("reports/no-mul-forwarding/utilization.rpt"),
        help="Modified design utilization.rpt path.",
    )

    parser.add_argument(
        "--baseline-label",
        default="Baseline",
        help="Label for the baseline design.",
    )

    parser.add_argument(
        "--modified-label",
        default="No MUL Forwarding",
        help="Label for the modified design.",
    )

    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("reports/comparison"),
        help="Output directory for plots and summary CSV.",
    )

    args = parser.parse_args()

    baseline = parse_vivado_utilization(args.baseline)
    modified = parse_vivado_utilization(args.modified)

    out_csv = args.out_dir / "utilization_summary.csv"
    out_png = args.out_dir / "utilization_percent_comparison.png"
    out_pdf = args.out_dir / "utilization_percent_comparison.pdf"

    write_summary_csv(
        out_csv=out_csv,
        baseline=baseline,
        modified=modified,
        baseline_label=args.baseline_label,
        modified_label=args.modified_label,
    )

    plot_utilization_percent(
        out_png=out_png,
        out_pdf=out_pdf,
        baseline=baseline,
        modified=modified,
        baseline_label=args.baseline_label,
        modified_label=args.modified_label,
    )

    print(f"Wrote {out_csv}")
    print(f"Wrote {out_png}")
    print(f"Wrote {out_pdf}")


if __name__ == "__main__":
    main()
