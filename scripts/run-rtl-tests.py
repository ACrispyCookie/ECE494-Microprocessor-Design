#!/usr/bin/env python3
"""Compile and run CV32E40P RTL assembly tests with sv2v + iverilog.

The flow is intentionally file-based:
  1. assemble rtl-tests/asm/<test>.S into program_imem.mem;
  2. convert the selected CV32E40P SystemVerilog sources to Verilog with sv2v;
  3. compile the converted RTL + generic testbench with iverilog;
  4. run vvp in a per-test working directory;
  5. generate expected_dmem.mem/expected_regfile.mem from the assembled program;
  6. let the RTL testbench compare final DMEM and regfile against those dumps.
"""
from __future__ import annotations

import argparse
import os
import shutil
import struct
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASM_DIR = ROOT / "rtl-tests" / "asm"
GOLDEN_DIR = ROOT / "rtl-tests" / "golden"
PREBUILT_DIR = ROOT / "rtl-tests" / "prebuilt"
TB = ROOT / "rtl-tests" / "tb" / "tb_cv32e40p_rtl.sv"
BUILD_ROOT = ROOT / "build" / "rtl-tests"
TOOLS_DIR = ROOT / "build" / "tools"
SV2V_VERSION = "v0.0.13"
SV2V_URL = f"https://github.com/zachjs/sv2v/releases/download/{SV2V_VERSION}/sv2v-Linux.zip"
DONE_ADDR = 0x0001_FFFC
DONE_MAGIC = 0x5555_AAAA
DMEM_WORDS = 4096

VERSIONS = {
    "baseline": "cv32e40p_baseline",
    "no_mul_forwarding": "cv32e40p_no_mul_forwarding",
    "no-mul-forwarding": "cv32e40p_no_mul_forwarding",
    "no_alu_forwarding": "cv32e40p_no_alu_forwarding",
    "no-alu-forwarding": "cv32e40p_no_alu_forwarding",
    "no_alu_mul_forwarding": "cv32e40p_no_alu_mul_forwarding",
    "no-alu-mul-forwarding": "cv32e40p_no_alu_mul_forwarding",
}

CV32_FILES = [
    "rtl/include/cv32e40p_apu_core_pkg.sv",
    "rtl/include/cv32e40p_fpu_pkg.sv",
    "rtl/include/cv32e40p_pkg.sv",
    "rtl/vendor/pulp_platform_common_cells/src/cf_math_pkg.sv",
    "rtl/vendor/pulp_platform_common_cells/src/lzc.sv",
    "rtl/vendor/pulp_platform_common_cells/src/rr_arb_tree.sv",
    "rtl/cv32e40p_alu.sv",
    "rtl/cv32e40p_alu_div.sv",
    "rtl/cv32e40p_ff_one.sv",
    "rtl/cv32e40p_popcnt.sv",
    "rtl/cv32e40p_compressed_decoder.sv",
    "rtl/cv32e40p_controller.sv",
    "rtl/cv32e40p_cs_registers.sv",
    "rtl/cv32e40p_decoder.sv",
    "rtl/cv32e40p_int_controller.sv",
    "rtl/cv32e40p_ex_stage.sv",
    "rtl/cv32e40p_hwloop_regs.sv",
    "rtl/cv32e40p_id_stage.sv",
    "rtl/cv32e40p_if_stage.sv",
    "rtl/cv32e40p_load_store_unit.sv",
    "rtl/cv32e40p_mult.sv",
    "rtl/cv32e40p_prefetch_buffer.sv",
    "rtl/cv32e40p_prefetch_controller.sv",
    "rtl/cv32e40p_obi_interface.sv",
    "rtl/cv32e40p_aligner.sv",
    "rtl/cv32e40p_sleep_unit.sv",
    "rtl/cv32e40p_apu_disp.sv",
    "rtl/cv32e40p_fifo.sv",
    "rtl/cv32e40p_register_file_ff.sv",
    "rtl/cv32e40p_core.sv",
    "rtl/cv32e40p_top.sv",
]

WRAPPER_FILES = [
    "zedboard-wrapper/cv32e40p_clock_gate.sv",
    "zedboard-wrapper/imem_bram.sv",
    "zedboard-wrapper/dmem_bram.sv",
    "zedboard-wrapper/zedboard_cv32e40p_wrapper.sv",
]


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


def prepend_known_tool_paths() -> None:
    extra = [
        ROOT.parent / ".local-bin",
        ROOT.parent / "tools" / "xpack-riscv-none-elf-gcc-15.2.0-1" / "bin",
    ]
    os.environ["PATH"] = os.pathsep.join(str(p) for p in extra if p.exists()) + os.pathsep + os.environ.get("PATH", "")


def path_candidates(name: str) -> list[Path]:
    seen: set[Path] = set()
    candidates: list[Path] = []
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        if not entry:
            continue
        candidate = Path(entry) / name
        if candidate.exists() and os.access(candidate, os.X_OK) and candidate not in seen:
            seen.add(candidate)
            candidates.append(candidate)
    return candidates


def tool_runs(path: Path, probe_args: list[str]) -> bool:
    try:
        proc = subprocess.run(
            [str(path), *probe_args],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0


def find_tool(name: str, *, probe_args: list[str] | None = None) -> str:
    candidates = path_candidates(name)
    if not candidates:
        raise SystemExit(f"Required tool not found in PATH: {name}")
    if probe_args is None:
        return str(candidates[0])
    for candidate in candidates:
        if tool_runs(candidate, probe_args):
            return str(candidate)
    tried = ", ".join(str(c) for c in candidates)
    raise SystemExit(f"Required tool found but none of the candidates ran successfully: {name}. Tried: {tried}")


def find_optional_tool(name: str, *, probe_args: list[str] | None = None) -> str | None:
    try:
        return find_tool(name, probe_args=probe_args)
    except SystemExit:
        return None


def find_iverilog_vvp_pair() -> tuple[str, str]:
    """Find an iverilog/vvp pair from the same installation.

    VVP bytecode is not forward/backward compatible across all Icarus versions.
    Prefer a sibling `vvp` next to each usable `iverilog`; this avoids compiling
    with a local iverilog wrapper and running with an older system vvp.
    """
    for iverilog in path_candidates("iverilog"):
        if not tool_runs(iverilog, ["-V"]):
            continue
        sibling_vvp = iverilog.parent / "vvp"
        if sibling_vvp.exists() and os.access(sibling_vvp, os.X_OK) and tool_runs(sibling_vvp, ["-V"]):
            return str(iverilog), str(sibling_vvp)

    # Fallback: both tools run, but may be from different installations.
    return (
        find_tool("iverilog", probe_args=["-V"]),
        find_tool("vvp", probe_args=["-V"]),
    )


def ensure_sv2v() -> str:
    path = shutil.which("sv2v")
    if path:
        return path

    bundled = ROOT.parent / "tools" / "sv2v-0.0.13" / "sv2v-Linux" / "sv2v"
    if bundled.exists():
        return str(bundled)

    target = TOOLS_DIR / "sv2v-0.0.13" / "sv2v-Linux" / "sv2v"
    if not target.exists():
        target.parent.parent.mkdir(parents=True, exist_ok=True)
        archive = target.parent.parent / "sv2v-Linux.zip"
        print(f"[SETUP] Downloading sv2v {SV2V_VERSION} to {archive}")
        urllib.request.urlretrieve(SV2V_URL, archive)
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(target.parent.parent)
        target.chmod(0o755)
    return str(target)


def assemble_test(test: str, workdir: Path, gcc: str, objcopy: str) -> Path:
    asm = ASM_DIR / f"{test}.S"
    if not asm.exists():
        raise SystemExit(f"Missing assembly test: {asm}")

    elf = workdir / f"{test}.elf"
    binary = workdir / f"{test}.bin"
    mem = workdir / "program_imem.mem"
    linker = workdir / "link.ld"
    linker.write_text(
        "ENTRY(_start)\n"
        "SECTIONS {\n"
        "  . = 0x00000000;\n"
        "  .text : { *(.text*) }\n"
        "  .rodata : { *(.rodata*) }\n"
        "}\n"
    )

    run([
        gcc, "-march=rv32im", "-mabi=ilp32", "-nostdlib", "-nostartfiles", "-T", str(linker),
        "-I", str(ASM_DIR), str(asm), "-o", str(elf),
    ], timeout=120)
    run([objcopy, "-O", "binary", str(elf), str(binary)], timeout=120)

    data = binary.read_bytes()
    if len(data) % 4:
        data += b"\x00" * (4 - (len(data) % 4))
    with mem.open("w") as f:
        f.write("@00000000\n")
        for (word,) in struct.iter_unpack("<I", data):
            f.write(f"{word:08x}\n")
    return elf


def generate_expected(elf: Path, workdir: Path, objdump: str) -> tuple[Path, Path]:
    generator = GOLDEN_DIR / "generate_expected.py"
    if not generator.exists():
        raise SystemExit(f"Missing golden generator: {generator}")
    run([
        sys.executable, str(generator),
        "--elf", str(elf),
        "--objdump", objdump,
        "--out-dir", str(workdir),
    ], timeout=120)
    expected_dmem = workdir / "expected_dmem.mem"
    expected_regfile = workdir / "expected_regfile.mem"
    if not expected_dmem.exists() or not expected_regfile.exists():
        raise SystemExit(f"Golden generator did not write expected dumps in {workdir}")
    return expected_dmem, expected_regfile


def build_sim(version: str, core_dir: Path, sv2v: str, iverilog: str, vvp: str, force: bool) -> Path:
    outdir = BUILD_ROOT / version
    outdir.mkdir(parents=True, exist_ok=True)
    converted = outdir / "cv32e40p_wrapper_iverilog.v"
    sim = outdir / "tb_cv32e40p_rtl.vvp"
    meta = outdir / "tb_cv32e40p_rtl.tools"
    tool_meta = f"iverilog={iverilog}\nvvp={vvp}\n"
    if sim.exists() and meta.exists() and meta.read_text() == tool_meta and not force:
        return sim

    sources = [str(core_dir / rel) for rel in CV32_FILES] + [str(ROOT / rel) for rel in WRAPPER_FILES]
    cmd = [
        sv2v,
        "--define=SYNTHESIS",
        "--define=VERILATOR",
        "-I", str(core_dir / "rtl" / "include"),
        "-I", str(core_dir / "rtl" / "vendor" / "pulp_platform_common_cells" / "include"),
        *sources,
    ]
    print(f"[BUILD] sv2v {version}")
    converted.write_text(run(cmd, capture=True, timeout=300).stdout)

    print(f"[BUILD] iverilog {version}")
    run([iverilog, "-g2012", "-Wall", "-o", str(sim), str(converted), str(TB)], timeout=300)
    meta.write_text(tool_meta)
    return sim


def run_one(version: str, sim: Path, test: str, gcc: str, objcopy: str, objdump: str, vvp: str, timeout_cycles: int) -> bool:
    workdir = BUILD_ROOT / version / test
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True)

    elf = assemble_test(test, workdir, gcc, objcopy)
    expected_dmem, expected_regfile = generate_expected(elf, workdir, objdump)
    program_mem = workdir / "program_imem.mem"
    return run_sim(version, sim, test, workdir, program_mem, expected_dmem, expected_regfile, vvp, timeout_cycles)


def run_one_prebuilt(version: str, sim: Path, test: str, vvp: str, timeout_cycles: int) -> bool:
    source_dir = PREBUILT_DIR / test
    required = ["program_imem.mem", "expected_dmem.mem", "expected_regfile.mem"]
    missing = [name for name in required if not (source_dir / name).exists()]
    if missing:
        raise SystemExit(
            "RISC-V compiler tools were not found and this test has no prebuilt files: "
            f"{test} (missing: {', '.join(missing)}). Install riscv-none-elf-gcc/binutils "
            "or regenerate rtl-tests/prebuilt/."
        )

    workdir = BUILD_ROOT / version / test
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True)
    program_mem = workdir / "program_imem.mem"
    expected_dmem = workdir / "expected_dmem.mem"
    expected_regfile = workdir / "expected_regfile.mem"
    shutil.copy2(source_dir / "program_imem.mem", program_mem)
    shutil.copy2(source_dir / "expected_dmem.mem", expected_dmem)
    shutil.copy2(source_dir / "expected_regfile.mem", expected_regfile)
    print(f"[PREBUILT] Using prebuilt program/golden files for {test}")
    return run_sim(version, sim, test, workdir, program_mem, expected_dmem, expected_regfile, vvp, timeout_cycles)


def run_sim(
    version: str,
    sim: Path,
    test: str,
    workdir: Path,
    program_mem: Path,
    expected_dmem: Path,
    expected_regfile: Path,
    vvp: str,
    timeout_cycles: int,
) -> bool:
    if not program_mem.exists():
        raise SystemExit(f"Missing program memory image: {program_mem}")
    dump = workdir / "dmem_dump.mem"
    reg_dump = workdir / "regfile_dump.mem"

    print(f"[RUN] {version}/{test}")
    proc = subprocess.run(
        [
            vvp, str(sim),
            f"+dump_file={dump}",
            f"+regfile_dump_file={reg_dump}",
            f"+expected_dmem_file={expected_dmem}",
            f"+expected_regfile_file={expected_regfile}",
            f"+dump_words={DMEM_WORDS}",
            f"+dmem_check_words={DMEM_WORDS}",
            f"+timeout_cycles={timeout_cycles}",
        ],
        cwd=workdir,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=120,
    )
    (workdir / "sim.log").write_text(proc.stdout)
    if proc.returncode != 0:
        print(proc.stdout)
        print(f"[FAIL] {version}/{test}: simulator returned {proc.returncode}")
        return False

    print(f"[PASS] {version}/{test}")
    return True


def parse_args() -> argparse.Namespace:
    tests = sorted(p.stem for p in ASM_DIR.glob("*.S") if p.name != "test_macros.S")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", "--versions", nargs="+", default=["baseline", "no_mul_forwarding", "no_alu_forwarding", "no_alu_mul_forwarding"], choices=sorted(VERSIONS))
    parser.add_argument("--test", "--tests", nargs="+", default=tests, choices=tests)
    parser.add_argument("--force-rebuild", action="store_true", help="Re-run sv2v and iverilog even if vvp already exists")
    parser.add_argument("--timeout-cycles", type=int, default=2000)
    return parser.parse_args()


def ensure_core_submodules(core_dir: Path) -> None:
    if not core_dir.exists():
        rel = core_dir.relative_to(ROOT)
        print(f"[SETUP] Initializing submodule {rel}")
        run(["git", "submodule", "update", "--init", "--recursive", "--", str(rel)], cwd=ROOT, timeout=600)
        return

    if (core_dir / ".git").exists():
        print(f"[SETUP] Initializing nested submodules under {core_dir.relative_to(ROOT)}")
        run(["git", "submodule", "update", "--init", "--recursive"], cwd=core_dir, timeout=600)


def main() -> int:
    args = parse_args()
    prepend_known_tool_paths()
    sv2v = ensure_sv2v()
    iverilog, vvp = find_iverilog_vvp_pair()
    gcc = find_optional_tool("riscv-none-elf-gcc", probe_args=["--version"])
    objcopy = find_optional_tool("riscv-none-elf-objcopy", probe_args=["--version"])
    objdump = find_optional_tool("riscv-none-elf-objdump", probe_args=["--version"])
    have_riscv_tools = bool(gcc and objcopy and objdump)
    print(f"[TOOLS] iverilog={iverilog}")
    print(f"[TOOLS] vvp={vvp}")
    if have_riscv_tools:
        print(f"[TOOLS] riscv-gcc={gcc}")
    else:
        print("[TOOLS] riscv-none-elf-gcc/binutils not found; using rtl-tests/prebuilt/*.mem")

    all_ok = True
    for requested_version in args.version:
        version = requested_version.replace("-", "_")
        core_dir = ROOT / VERSIONS[requested_version]
        ensure_core_submodules(core_dir)
        sim = build_sim(version, core_dir, sv2v, iverilog, vvp, args.force_rebuild)
        for test in args.test:
            if have_riscv_tools:
                all_ok &= run_one(version, sim, test, gcc, objcopy, objdump, vvp, args.timeout_cycles)
            else:
                all_ok &= run_one_prebuilt(version, sim, test, vvp, args.timeout_cycles)

    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
