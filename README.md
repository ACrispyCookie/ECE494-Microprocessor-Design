# ECE494 Microprocessor Design — CV32E40P forwarding experiments

This repository compares several CV32E40P RTL variants on a minimal ZedBoard-style wrapper.  The flow keeps each RTL variant in a separate git submodule and uses shared scripts for RTL simulation, Vivado project generation, report export, and comparison plots.

## RTL variants

```text
experiment name          RTL submodule directory              default clock
baseline                 cv32e40p_baseline                    15.000 ns
no-mul-forwarding        cv32e40p_no_mul_forwarding           14.000 ns
no-alu-forwarding        cv32e40p_no_alu_forwarding           15.000 ns
no-alu-mul-forwarding    cv32e40p_no_alu_mul_forwarding       15.000 ns
```

The experiment name is the value passed to `make EXPERIMENT=...`, `report.sh --experiment ...`, and the Vivado project Tcl `--experiment ...` option.  The RTL-test runner accepts both hyphenated and underscored aliases, for example `no-mul-forwarding` and `no_mul_forwarding`.

## One-time setup

Initialize the CV32E40P submodules and their nested vendor submodules:

```bash
git submodule update --init --recursive
```

If Vivado is not on `PATH`, set `VIVADO` explicitly:

```bash
export VIVADO=/path/to/Vivado/2022.2/bin/vivado
```

## Tool dependencies

The project uses different tools depending on the flow:

```text
flow                         required tools
---------------------------  --------------------------------------------------
Vivado project/reports        Vivado 2022.2 or compatible Vivado installation
RTL tests                     Python 3, make, Icarus Verilog (iverilog + vvp),
                              RISC-V bare-metal GNU toolchain, sv2v
RTL benchmarks                Python 3, make, Icarus Verilog (iverilog + vvp),
                              RISC-V bare-metal GNU toolchain, sv2v
Plot regeneration             Python 3 only for the SVG plot scripts in scripts/
```

For the RTL tests and RTL benchmarks, the RISC-V toolchain must provide these executables on `PATH`:

```text
riscv-none-elf-gcc
riscv-none-elf-objcopy
riscv-none-elf-objdump
```

The benchmark flow specifically compiles freestanding RV32IM C programs with `riscv-none-elf-gcc`, then uses `riscv-none-elf-objcopy` to create the IMEM/DMEM images loaded by the benchmark testbench.  If these tools are missing, `make rtl-tests` and `make rtl-benchmarks` will fail before simulation.

A typical local setup is:

```bash
export PATH=/path/to/riscv-toolchain/bin:$PATH
export VIVADO=/path/to/Vivado/2022.2/bin/vivado
```

`sv2v` is needed because Icarus Verilog cannot parse all CV32E40P SystemVerilog sources directly.  If `sv2v` is not already installed, `scripts/run-rtl-tests.py` and `scripts/run-rtl-benchmarks.py` try to use a bundled checkout under `../tools/sv2v-0.0.13/` or download the pinned Linux release into `build/tools/`.

No extra Python packages are required for the main regression/benchmark/report scripts; they use the Python standard library and generate SVG plots directly.  The standalone exploratory scripts `scripts/plot-execution-time-change.py` and `scripts/plot-break-even-frequency.py` are optional and require `matplotlib`/`numpy` if used.

## RTL testbench flow

The RTL tests live under `rtl-tests/` and are run by `scripts/run-rtl-tests.py`.  The runner assembles the test program, converts CV32E40P SystemVerilog with `sv2v`, compiles with `iverilog`, runs `vvp`, and compares final DMEM/register-file state against generated golden dumps.

Run the full RTL regression for all variants:

```bash
make rtl-tests
```

Run one variant:

```bash
make rtl-tests-baseline
make rtl-tests-no-mul-forwarding
make rtl-tests-no-alu-forwarding
make rtl-tests-no-alu-mul-forwarding
```

Focused examples:

```bash
python3 scripts/run-rtl-tests.py --version baseline --test alu_load_store
python3 scripts/run-rtl-tests.py --version no-mul-forwarding --test mul_dependency_matrix
python3 scripts/run-rtl-tests.py --version no-alu-forwarding --test alu_dependency_matrix
python3 scripts/run-rtl-tests.py --version no-alu-mul-forwarding --test mixed_dependency_stress
python3 scripts/run-rtl-tests.py --force-rebuild
```

Per-test outputs are written under:

```text
build/rtl-tests/<version>/<test>/
```

Important files there include `program_imem.mem`, `expected_dmem.mem`, `expected_regfile.mem`, `dmem_dump.mem`, `regfile_dump.mem`, and `sim.log`.

## RTL benchmark flow

The C benchmarks live under `benchmarks/src/` and are run by `scripts/run-rtl-benchmarks.py`.  This flow is separate from the assembly correctness regression: it builds bare-metal RV32IM C workloads, initializes both instruction and data memories, runs a larger benchmark testbench, and records cycle metrics from memory-mapped start/stop/DONE stores.

Available benchmarks:

```text
vvadd multiply median sort rsort mm dhrystone
```

Run all benchmarks on all RTL variants:

```bash
make rtl-benchmarks
# equivalent:
python3 scripts/run-rtl-benchmarks.py --version all --benchmark all
```

Run one RTL variant and one benchmark:

```bash
python3 scripts/run-rtl-benchmarks.py --version baseline --benchmark vvadd
python3 scripts/run-rtl-benchmarks.py --version 1 --benchmark multiply      # 1 = no-mul-forwarding
python3 scripts/run-rtl-benchmarks.py --version 2 --benchmark sort          # 2 = no-alu-forwarding
python3 scripts/run-rtl-benchmarks.py --version 3 --benchmark mm            # 3 = no-alu-mul-forwarding
```

Make targets are also provided:

```bash
make rtl-benchmarks-baseline RTL_BENCH_ARGS="--benchmark vvadd"
make rtl-benchmarks-no-mul-forwarding RTL_BENCH_ARGS="--benchmark all"
make rtl-benchmarks-no-alu-forwarding RTL_BENCH_ARGS="--benchmark median sort"
make rtl-benchmarks-no-alu-mul-forwarding RTL_BENCH_ARGS="--benchmark mm dhrystone"
```

Per-run artifacts are written under:

```text
build/rtl-benchmarks/<version>/<benchmark>/
```

Important files there include `program_imem.mem`, `program_dmem.mem`, `<benchmark>.elf`, `image_sizes.txt`, and `sim.log`.  The benchmark testbench prints a metric line of the form:

```text
[METRIC] total_cycles=<cycles> roi_cycles=<cycles> return_code=<code> signature=0x<hex>
```

Summary reports are regenerated at:

```text
reports/benchmarks/benchmark_results.csv
reports/benchmarks/benchmark_results.md
```

The benchmark testbench uses 128 KiB IMEM and 128 KiB DMEM for simulation only.  The Vivado wrapper defaults remain unchanged for the FPGA timing/utilization flow, so the benchmark memory-size increase does not affect the existing implementation comparisons.

## Vivado project creation

Create/update a Vivado project for one variant:

```bash
make baseline
make no-mul-forwarding
make no-alu-forwarding
make no-alu-mul-forwarding
```

Equivalent explicit form:

```bash
make EXPERIMENT=baseline all
make EXPERIMENT=no-mul-forwarding all
```

Generated projects are placed under:

```text
build/vivado-<experiment>/cv32e40p-zedboard-project.xpr
```

The project-creation Tcl is:

```bash
vivado -mode batch -source cv32e40p-zedboard-project.tcl \
  -tclargs --experiment baseline
```

Optional Tcl arguments include:

```text
--experiment <baseline|no-mul-forwarding|no-alu-forwarding|no-alu-mul-forwarding>
--core_dir <path-to-cv32e40p-checkout>
--build_dir <path>
--project_name <name>
--clock_period <period-ns>
```

## Vivado reports and plots

Recommended full comparison command:

```bash
./report.sh --comparison --report all --create-projects --yes --stage post-implementation
```

Equivalent Make target:

```bash
make reports
```

This command:

```text
1. creates/updates Vivado projects for all built-in variants;
2. runs the selected post-implementation report flow;
3. writes per-variant raw reports/CSVs/metadata;
4. regenerates summary CSVs and SVG comparison plots.
```

Single-variant examples:

```bash
./report.sh --experiment baseline --report all --create-projects --yes --stage post-implementation
./report.sh --experiment no-mul-forwarding --report timing --yes --stage post-synthesis
./report.sh --experiment no-alu-forwarding --report utilization --yes
./report.sh --experiment no-alu-mul-forwarding --report path-distribution --yes
```

Report type aliases:

```text
all                utilization + timing + path CSV + power
timing             timing summary + worst paths + path CSV
timing-summary     timing_summary_1000_paths.rpt
worst-paths        worst_1000_paths.rpt + critical_paths_top10.rpt
path-csv           timing_paths.csv
path-distribution  path-csv + timing plots
utilization        utilization.rpt + utilization_hierarchical.rpt
power              power.rpt + power plots
```

Report stage choices:

```text
auto                 open impl_1 if available, otherwise synthesize and report post-synthesis
post-synthesis       synthesize current sources and report the post-synthesis netlist
post-implementation  report an implemented design; with --create-projects the script can run
                     an in-memory synth/opt/place/route flow before exporting reports
```

Outputs:

```text
reports/<experiment>/                  raw Vivado reports, timing_paths.csv, metadata.txt
reports/summary/*.csv                  comparison summaries
reports/plots/*.svg                    comparison plots
```

Useful generated reports:

```text
reports/<experiment>/timing_summary_1000_paths.rpt
reports/<experiment>/critical_paths_top10.rpt
reports/<experiment>/worst_1000_paths.rpt
reports/<experiment>/utilization.rpt
reports/<experiment>/utilization_hierarchical.rpt
reports/<experiment>/power.rpt
```

## Regenerating plots from existing reports

If `reports/*/timing_paths.csv`, utilization reports, and power reports already exist, regenerate plots without rerunning Vivado:

```bash
python3 scripts/plot-timing.py
python3 scripts/plot-utilization.py
python3 scripts/plot-power.py
python3 scripts/plot-presentation-summary.py
```

The datapath-delay histogram spacing is controlled in `scripts/plot-timing.py` by:

```python
HISTOGRAM_BIN_GAP_PX = 8
```

Increase this value for more space between adjacent histogram bins; decrease it for wider grouped bars.

## Opening designs in the Vivado GUI

The report flow can generate reports from an in-memory implementation.  That is enough for `.rpt`/`.csv` output, but it does not necessarily leave a completed GUI `impl_1` run inside the `.xpr`.  If `Open Implemented Design` is disabled after opening the `.xpr`, run implementation as a normal Vivado project run:

```tcl
open_project build/vivado-baseline/cv32e40p-zedboard-project.xpr
launch_runs synth_1 -jobs 8
wait_on_run synth_1
launch_runs impl_1 -to_step route_design -jobs 8
wait_on_run impl_1
open_run impl_1
start_gui
```

Change the `build/vivado-<experiment>/...` path for other variants.

## Common checks

```bash
bash -n report.sh
python3 -m py_compile scripts/run-rtl-tests.py scripts/plot-timing.py scripts/plot-utilization.py scripts/plot-power.py scripts/plot-presentation-summary.py
make -n baseline
make -n no-mul-forwarding
make -n no-alu-forwarding
make -n no-alu-mul-forwarding
make -n reports
```
