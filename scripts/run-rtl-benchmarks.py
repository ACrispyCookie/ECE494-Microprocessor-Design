#!/usr/bin/env python3
"""Build and run bare-metal C benchmarks on CV32E40P RTL variants.

The flow is intentionally separate from scripts/run-rtl-tests.py.  The assembly
regression flow is for correctness with a Python architectural golden model;
this benchmark flow is for cycle-count measurements of C workloads.
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import os
import re
import shutil
import struct
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BENCH_SRC_DIR = ROOT / "benchmarks" / "src"
BENCH_RUNTIME_DIR = ROOT / "benchmarks" / "runtime"
BENCH_TB = ROOT / "rtl-tests" / "tb" / "tb_cv32e40p_benchmark.sv"
BUILD_ROOT = ROOT / "build" / "rtl-benchmarks"
REPORT_DIR = ROOT / "reports" / "benchmarks"
RTL_RUNNER_PATH = ROOT / "scripts" / "run-rtl-tests.py"
IMEM_WORDS = 32768
DMEM_WORDS = 32768
DEFAULT_TIMEOUT_CYCLES = 2_000_000
DEFAULT_BENCHMARKS = ["vvadd", "multiply", "median", "sort", "rsort", "mm", "dhrystone"]
DEFAULT_VERSIONS = ["baseline", "no_mul_forwarding", "no_alu_forwarding", "no_alu_mul_forwarding"]
VERSION_ALIASES = {
    "all": "all",
    "baseline": "baseline",
    "0": "baseline",
    "no_mul_forwarding": "no_mul_forwarding",
    "no-mul-forwarding": "no_mul_forwarding",
    "mul": "no_mul_forwarding",
    "1": "no_mul_forwarding",
    "no_alu_forwarding": "no_alu_forwarding",
    "no-alu-forwarding": "no_alu_forwarding",
    "alu": "no_alu_forwarding",
    "2": "no_alu_forwarding",
    "no_alu_mul_forwarding": "no_alu_mul_forwarding",
    "no-alu-mul-forwarding": "no_alu_mul_forwarding",
    "alu-mul": "no_alu_mul_forwarding",
    "3": "no_alu_mul_forwarding",
}
CLOCK_PERIOD_NS = {
    "baseline": 15.000,
    "no_mul_forwarding": 14.000,
    "no_alu_forwarding": 15.000,
    "no_alu_mul_forwarding": 15.000,
}


@dataclass(frozen=True)
class Metrics:
    total_cycles: int
    roi_cycles: int
    return_code: int
    signature: str
    status: str


def load_rtl_runner():
    spec = importlib.util.spec_from_file_location("run_rtl_tests", RTL_RUNNER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {RTL_RUNNER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def resolve_versions(requested: list[str]) -> list[str]:
    resolved: list[str] = []
    for item in requested:
        key = item.strip()
        if key not in VERSION_ALIASES:
            raise SystemExit(f"Unknown RTL version '{item}'. Choices: all, baseline, 1/no-mul-forwarding, 2/no-alu-forwarding, 3/no-alu-mul-forwarding")
        alias = VERSION_ALIASES[key]
        if alias == "all":
            for version in DEFAULT_VERSIONS:
                if version not in resolved:
                    resolved.append(version)
        elif alias not in resolved:
            resolved.append(alias)
    return resolved


def available_benchmarks() -> list[str]:
    found = sorted(p.stem for p in BENCH_SRC_DIR.glob("*.c"))
    return [b for b in DEFAULT_BENCHMARKS if b in found] + [b for b in found if b not in DEFAULT_BENCHMARKS]


def resolve_benchmarks(requested: list[str]) -> list[str]:
    available = available_benchmarks()
    if not available:
        raise SystemExit(f"No benchmark sources found under {BENCH_SRC_DIR}")
    resolved: list[str] = []
    for item in requested:
        key = item.strip()
        if key == "all":
            for bench in available:
                if bench not in resolved:
                    resolved.append(bench)
        elif key in available:
            if key not in resolved:
                resolved.append(key)
        else:
            raise SystemExit(f"Unknown benchmark '{item}'. Choices: all, {', '.join(available)}")
    return resolved


def run(cmd: list[str], *, cwd: Path = ROOT, timeout: int = 300, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
        timeout=timeout,
        check=True,
    )


def words_from_bytes(data: bytes) -> list[str]:
    if len(data) % 4:
        data += b"\x00" * (4 - (len(data) % 4))
    return [f"{word:08x}" for (word,) in struct.iter_unpack("<I", data)]


def write_mem(path: Path, data: bytes, max_words: int) -> int:
    words = words_from_bytes(data)
    if len(words) > max_words:
        raise SystemExit(f"{path.name} image has {len(words)} words, exceeds memory depth {max_words}")
    path.write_text("@00000000\n" + "\n".join(words) + ("\n" if words else ""))
    return len(words)


def build_benchmark(bench: str, workdir: Path, gcc: str, objcopy: str) -> Path:
    src = BENCH_SRC_DIR / f"{bench}.c"
    if not src.exists():
        raise SystemExit(f"Missing benchmark source: {src}")
    workdir.mkdir(parents=True, exist_ok=True)
    elf = workdir / f"{bench}.elf"
    linker = BENCH_RUNTIME_DIR / "link.ld"
    crt0 = BENCH_RUNTIME_DIR / "crt0.S"
    support = BENCH_RUNTIME_DIR / "bench_support.c"
    cmd = [
        gcc,
        "-march=rv32im",
        "-mabi=ilp32",
        "-O2",
        "-ffreestanding",
        "-fno-builtin",
        "-fno-pic",
        "-fno-asynchronous-unwind-tables",
        "-fno-unwind-tables",
        "-msmall-data-limit=0",
        "-nostdlib",
        "-nostartfiles",
        "-T", str(linker),
        "-I", str(BENCH_RUNTIME_DIR),
        str(crt0), str(support), str(src),
        "-lgcc",
        "-o", str(elf),
    ]
    run(cmd, timeout=120)
    run([objcopy, "-O", "binary", "-j", ".text", str(elf), str(workdir / "program_imem.bin")], timeout=60)
    run([objcopy, "-O", "binary", "-j", ".data", str(elf), str(workdir / "program_dmem.bin")], timeout=60)
    imem_words = write_mem(workdir / "program_imem.mem", (workdir / "program_imem.bin").read_bytes(), IMEM_WORDS)
    dmem_words = write_mem(workdir / "program_dmem.mem", (workdir / "program_dmem.bin").read_bytes(), DMEM_WORDS)
    (workdir / "image_sizes.txt").write_text(f"imem_words={imem_words}\ndmem_words={dmem_words}\n")
    return elf


def build_sim(version: str, core_dir: Path, sv2v: str, iverilog: str, force: bool) -> Path:
    rtl = load_rtl_runner()
    outdir = BUILD_ROOT / version
    outdir.mkdir(parents=True, exist_ok=True)
    converted = outdir / "cv32e40p_benchmark_iverilog.v"
    sim = outdir / "tb_cv32e40p_benchmark.vvp"
    meta = outdir / "tb_cv32e40p_benchmark.tools"
    tool_meta = f"sv2v={sv2v}\niverilog={iverilog}\ntb={BENCH_TB}\nimem_words={IMEM_WORDS}\ndmem_words={DMEM_WORDS}\n"
    if sim.exists() and meta.exists() and meta.read_text() == tool_meta and not force:
        return sim
    sources = [str(core_dir / rel) for rel in rtl.CV32_FILES] + [str(ROOT / rel) for rel in rtl.WRAPPER_FILES]
    cmd = [
        sv2v,
        "--define=SYNTHESIS",
        "--define=VERILATOR",
        "-I", str(core_dir / "rtl" / "include"),
        "-I", str(core_dir / "rtl" / "vendor" / "pulp_platform_common_cells" / "include"),
        *sources,
    ]
    print(f"[BUILD] sv2v benchmark {version}")
    converted.write_text(run(cmd, capture=True, timeout=300).stdout)
    print(f"[BUILD] iverilog benchmark {version}")
    run([iverilog, "-g2012", "-Wall", "-o", str(sim), str(converted), str(BENCH_TB)], timeout=300)
    meta.write_text(tool_meta)
    return sim


def parse_metrics(log_text: str) -> Metrics:
    metric_re = re.search(r"\[METRIC\]\s+total_cycles=(\d+)\s+roi_cycles=(-?\d+)\s+return_code=(-?\d+)\s+signature=(0x[0-9a-fA-F]+)", log_text)
    if not metric_re:
        return Metrics(-1, -1, -1, "0x00000000", "FAIL")
    status = "PASS" if "[PASS] RTL benchmark completed successfully" in log_text else "FAIL"
    return Metrics(
        total_cycles=int(metric_re.group(1)),
        roi_cycles=int(metric_re.group(2)),
        return_code=int(metric_re.group(3)),
        signature=metric_re.group(4).lower(),
        status=status,
    )


def run_one(version: str, bench: str, sim: Path, gcc: str, objcopy: str, vvp: str, timeout_cycles: int) -> dict[str, object]:
    workdir = BUILD_ROOT / version / bench
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True)
    print(f"[BUILD] benchmark {bench} for {version}")
    build_benchmark(bench, workdir, gcc, objcopy)
    print(f"[RUN] {version}/{bench}")
    proc = subprocess.run(
        [vvp, str(sim), f"+timeout_cycles={timeout_cycles}"],
        cwd=workdir,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=max(120, min(600, timeout_cycles // 1000 + 120)),
    )
    log_text = proc.stdout
    (workdir / "sim.log").write_text(log_text)
    metrics = parse_metrics(log_text)
    if proc.returncode != 0 or metrics.status != "PASS":
        print(log_text)
        print(f"[FAIL] {version}/{bench}: simulator returned {proc.returncode}, status={metrics.status}")
        status = "FAIL"
    else:
        print(f"[PASS] {version}/{bench}: total_cycles={metrics.total_cycles} roi_cycles={metrics.roi_cycles} signature={metrics.signature}")
        status = "PASS"
    clock_ns = CLOCK_PERIOD_NS[version]
    roi_time_ns = metrics.roi_cycles * clock_ns if metrics.roi_cycles >= 0 else -1
    total_time_ns = metrics.total_cycles * clock_ns if metrics.total_cycles >= 0 else -1
    return {
        "version": version,
        "benchmark": bench,
        "status": status,
        "total_cycles": metrics.total_cycles,
        "roi_cycles": metrics.roi_cycles,
        "clock_period_ns": f"{clock_ns:.3f}",
        "roi_time_ns": f"{roi_time_ns:.3f}" if roi_time_ns >= 0 else "-1",
        "total_time_ns": f"{total_time_ns:.3f}" if total_time_ns >= 0 else "-1",
        "return_code": metrics.return_code,
        "signature": metrics.signature,
        "log": str(workdir / "sim.log"),
    }


def write_reports(rows: list[dict[str, object]]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = REPORT_DIR / "benchmark_results.csv"
    fields = ["version", "benchmark", "status", "total_cycles", "roi_cycles", "clock_period_ns", "roi_time_ns", "total_time_ns", "return_code", "signature", "log"]
    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    md_path = REPORT_DIR / "benchmark_results.md"
    lines = ["# CV32E40P RTL benchmark results", "", "```text", "version                  benchmark   status  roi_cycles  total_cycles  clk_ns  roi_time_ns  signature"]
    for r in rows:
        lines.append(f"{r['version']:<24} {r['benchmark']:<11} {r['status']:<6} {r['roi_cycles']:>10}  {r['total_cycles']:>12}  {r['clock_period_ns']:>6}  {r['roi_time_ns']:>11}  {r['signature']}")
    lines.extend(["```", "", f"CSV: `{csv_path}`"])
    md_path.write_text("\n".join(lines) + "\n")
    print(f"[REPORT] {csv_path}")
    print(f"[REPORT] {md_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", "--versions", nargs="+", default=["all"], help="RTL version(s): all, baseline, 1/no-mul-forwarding, 2/no-alu-forwarding, 3/no-alu-mul-forwarding")
    parser.add_argument("--benchmark", "--benchmarks", "--test", "--tests", nargs="+", default=["all"], help="Benchmark(s): all, vvadd, multiply, median, sort, rsort, mm, dhrystone")
    parser.add_argument("--timeout-cycles", type=int, default=DEFAULT_TIMEOUT_CYCLES)
    parser.add_argument("--force-rebuild", action="store_true", help="Re-run sv2v/iverilog even if the benchmark simulator already exists")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    versions = resolve_versions(args.version)
    benchmarks = resolve_benchmarks(args.benchmark)
    rtl = load_rtl_runner()
    rtl.prepend_known_tool_paths()
    sv2v = rtl.ensure_sv2v()
    iverilog, vvp = rtl.find_iverilog_vvp_pair()
    gcc = rtl.find_tool("riscv-none-elf-gcc", probe_args=["--version"])
    objcopy = rtl.find_tool("riscv-none-elf-objcopy", probe_args=["--version"])
    print(f"[TOOLS] iverilog={iverilog}")
    print(f"[TOOLS] vvp={vvp}")
    print(f"[TOOLS] gcc={gcc}")

    rows: list[dict[str, object]] = []
    all_ok = True
    for version in versions:
        requested_name = version.replace("_", "-")
        core_dir = ROOT / rtl.VERSIONS[requested_name]
        rtl.ensure_core_submodules(core_dir)
        sim = build_sim(version, core_dir, sv2v, iverilog, args.force_rebuild)
        for bench in benchmarks:
            row = run_one(version, bench, sim, gcc, objcopy, vvp, args.timeout_cycles)
            rows.append(row)
            all_ok &= row["status"] == "PASS"
    write_reports(rows)
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
