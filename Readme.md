## cv32e40p on ZedBoard

### Getting Started

This repository is a Vivado/ZedBoard experiment harness around two side-by-side
`cv32e40p` submodule checkouts:

```text
parent repo main branch
├── cv32e40p_baseline          # cv32e40p branch: master
└── cv32e40p_no_mul_forwarding # cv32e40p branch: uth_tsiantosd_20260522
```

Clone and initialize both submodules with:

```cmd
git clone --recurse-submodules https://github.com/TsiantosD/ECE494-Microprocessor-Design
cd ECE494-Microprocessor-Design
git submodule update --init --recursive
```

Create the baseline Vivado project:

```cmd
make baseline
```

Create the modified/no-mul-forwarding Vivado project:

```cmd
make no-mul-forwarding
```

You can also select the experiment explicitly:

```cmd
make EXPERIMENT=baseline
make EXPERIMENT=no-mul-forwarding
```

The `Makefile` creates and deletes Vivado projects. Use `make clean` to delete
generated Vivado/build artifacts.

### Project Structure

```cmd
.
├── build                                # contains generated Vivado projects
│   ├── vivado-baseline
│   └── vivado-no-mul-forwarding
├── cv32e40p_baseline                    # baseline cv32e40p submodule, branch master
├── cv32e40p_no_mul_forwarding           # modified cv32e40p submodule, branch uth_tsiantosd_20260522
├── cv32e40p-zedboard-project.tcl        # generates Vivado projects; selects core checkout by experiment
├── Makefile                             # create/delete Vivado projects
├── Readme.md
├── parse-reports-scripts
├── reports
├── report.sh                            # canonical CLI for reports/comparison plots
├── sw
└── zedboard-wrapper                     # ZedBoard-specific design (.sv) and constraints (.xdc) files
```

### Project Purpose

The purpose of this project is to compare the original CPU design and a modified
one in the following aspects:

1. Utilization
   - LUTs
   - FFs
   - DSPs
   - BRAMs

2. Timing
   - WNS
   - estimated/swept Fmax
   - critical path start/end
   - logic delay vs net delay

3. Path distribution
   - slack histogram
   - datapath delay histogram
   - critical path categories per hierarchy

4. Power
   - vectorless estimate
   - SAIF-based estimate from simulation

5. Performance
   - cycles until completion for small benchmarks
   - Fmax
   - estimated execution time = cycles / Fmax

### Workflow

The parent repository can stay on `main`. The experiment is selected by the
Vivado project-generation command instead of by switching both the parent branch
and the submodule branch.

Baseline flow:

```cmd
make baseline
# Run synthesis/implementation in build/vivado-baseline/cv32e40p-zedboard-project.xpr
./report.sh -e baseline -r all -y
```

Modified flow:

```cmd
make no-mul-forwarding
# Run synthesis/implementation in build/vivado-no-mul-forwarding/cv32e40p-zedboard-project.xpr
./report.sh -e no-mul-forwarding -r all -y
```

For custom experiments, pass an explicit core checkout path:

```cmd
make EXPERIMENT=my-experiment CORE_DIR=/path/to/cv32e40p_checkout
```

### Creating, Parsing, and Plotting Reports

`report.sh` is the canonical report CLI for this project. It can run each report
individually for one design, or run the same report flow for both designs and
regenerate comparison artifacts.

Single-design examples:

```cmd
./report.sh -e baseline -r utilization -y
./report.sh -e baseline -r timing-summary -y
./report.sh -e baseline -r worst-paths -y
./report.sh -e baseline -r path-distribution -y
./report.sh -e no-mul-forwarding -r timing -y
```

Comparison examples:

```cmd
./report.sh --comparison -r utilization -y
./report.sh --comparison -r timing -y
./report.sh --comparison -r all -y
```

Report type meanings:

```text
utilization        -> utilization.rpt, utilization_hierarchical.rpt
timing-summary     -> timing_summary_1000_paths.rpt
worst-paths        -> worst_1000_paths.rpt, critical_paths_top10.rpt
path-csv           -> timing_paths.csv
path-distribution  -> alias for path-csv plus timing/path plots in comparison mode
timing             -> timing-summary + worst-paths + path-csv
all                -> utilization + timing-summary + worst-paths + path-csv
```

Power and benchmark-performance reporting are intentionally not part of `all`
yet; those will be added later once the methodology is decided.

The script chooses the default Vivado project path from the experiment name:

```text
baseline          -> build/vivado-baseline/cv32e40p-zedboard-project.xpr
no-mul-forwarding -> build/vivado-no-mul-forwarding/cv32e40p-zedboard-project.xpr
```

If a built-in project is missing, `report.sh` creates it automatically. To force
project regeneration before reporting, pass `--create-projects`. To require an
already-existing project, pass `--no-create-projects`.

Comparison outputs:

```text
reports/summary/utilization_compare.csv
reports/summary/timing_metrics.csv
reports/summary/path_distribution.csv
reports/plots/utilization_compare.svg
reports/plots/slack_histogram.svg
reports/plots/datapath_delay_histogram.svg
```

Makefile convenience targets call the same CLI:

```cmd
make reports              # ./report.sh --comparison -r all -y
make utilization-reports  # ./report.sh --comparison -r utilization -y
make timing-reports       # ./report.sh --comparison -r timing -y
make utilization-plots
make timing-plots
```

In this container, Vivado implementation launch can crash in vendor
licensing/WebTalk host-enumeration code, while synthesis succeeds. When an
implemented `impl_1` run is unavailable, the report exporter generates clearly
labeled post-synthesis reports and records this in:

```text
reports/<experiment>/metadata.txt
report_stage=post_synthesis
```
