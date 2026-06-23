#!/usr/bin/env python3
"""Shared SVG styling helpers for report plots."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlotStyle:
    """Presentation/report style switches used by the standard-library SVG plots."""

    black_white: bool = False
    clean: bool = False

    @property
    def show_titles(self) -> bool:
        return not self.clean

    @property
    def show_value_labels(self) -> bool:
        return not self.clean

    @property
    def palette(self) -> tuple[str, ...]:
        if self.black_white:
            # Ordered from dark to light.  Kept distinct in grayscale printouts.
            return ("#111111", "#555555", "#999999", "#d0d0d0", "#ffffff")
        return ("#2563eb", "#dc2626", "#16a34a", "#9333ea", "#ea580c", "#0891b2", "#4f46e5", "#be123c")

    @property
    def axis_color(self) -> str:
        return "#111111" if self.black_white else "#374151"

    @property
    def tick_color(self) -> str:
        return "#111111" if self.black_white else "#6b7280"

    @property
    def grid_color(self) -> str:
        return "#d9d9d9" if self.black_white else "#e5e7eb"


def add_style_arguments(parser) -> None:
    parser.add_argument(
        "--black-and-white",
        "--bw",
        action="store_true",
        help="render plot with grayscale fills suitable for black-and-white printing",
    )
    parser.add_argument(
        "--report-style",
        action="store_true",
        help="report-ready style: black-and-white, no title/subtitle, no value labels; keep axes, ticks and legend",
    )


def style_from_args(args) -> PlotStyle:
    return PlotStyle(black_white=bool(args.black_and_white or args.report_style), clean=bool(args.report_style))


def color_for(name: str, index: int, style: PlotStyle, color_map: dict[str, str] | None = None) -> str:
    if not style.black_white and color_map and name in color_map:
        return color_map[name]
    return style.palette[index % len(style.palette)]


def bar_extra_attrs(index: int, style: PlotStyle) -> str:
    """Return SVG attrs that add grayscale stroke contrast in report mode."""

    if not style.black_white:
        return ' rx="3"'
    stroke = "#000000" if index != 0 else "#111111"
    return f' stroke="{stroke}" stroke-width="1.2" rx="2"'


def svg_style_block(style: PlotStyle, label_font_size: int = 13, axis_font_size: int = 16, tick_font_size: int = 14) -> str:
    return (
        "<style>"
        "text{font-family:Inter,Arial,sans-serif;fill:#111111}"
        ".title{font-size:30px;font-weight:700}"
        ".subtitle{font-size:15px;fill:#4b5563}"
        f".axis{{font-size:{axis_font_size}px;font-weight:700;fill:{style.axis_color}}}"
        f".tick{{font-size:{tick_font_size}px;fill:{style.tick_color}}}"
        f".label{{font-size:{label_font_size}px;fill:#111111}}"
        ".legend{font-size:15px;fill:#111111}"
        f".grid{{stroke:{style.grid_color};stroke-width:1}}"
        f".axisline{{stroke:{style.axis_color};stroke-width:1.7}}"
        "</style>"
    )
