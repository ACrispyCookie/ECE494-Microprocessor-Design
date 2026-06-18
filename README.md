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

The submission ZIP already contains the CV32E40P RTL variant directories (`cv32e40p_*`) as normal source folders.  After unzipping the submission, **do not run** `git submodule update --init --recursive`; the ZIP is intentionally not a git repository.

If Vivado is not on `PATH`, set `VIVADO` explicitly:

```bash
export VIVADO=/path/to/Vivado/2022.2/bin/vivado
```

## RTL testbench flow

The RTL tests live under `rtl-tests/` and are run by `scripts/run-rtl-tests.py`.  The runner converts CV32E40P SystemVerilog with `sv2v`, compiles with `iverilog`, runs `vvp`, and compares final DMEM/register-file state against golden dumps.

The submission includes prebuilt files under `rtl-tests/prebuilt/` (`program_imem.mem`, `expected_dmem.mem`, `expected_regfile.mem`) for every provided assembly test.  Therefore `make rtl-tests` does **not** require a 1GB RISC-V GCC toolchain just to run the delivered tests.  If `riscv-none-elf-gcc`, `riscv-none-elf-objcopy`, and `riscv-none-elf-objdump` are available on `PATH`, the runner regenerates the memories from `rtl-tests/asm/*.S`; otherwise it uses the prebuilt `.mem` files.

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
