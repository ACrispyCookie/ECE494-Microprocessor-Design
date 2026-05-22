## cv32e40p on ZedBoard

### Getting Started
To clone this repo and create the vivado project, you need to run the following commands:

```cmd
git clone --recurse-submodules https://github.com/TsiantosD/ECE494-Microprocessor-Design
cd ECE494-Microprocessor-Design
make
```

The `Makefile` creates and deletes the Vivado project. Use `make clean` to delete the Vivado project.

### Project Structure

```cmd
.
├── build                           # contains the Vivado project
├── cv32e40p                        # contains the cv32e40p github repo
├── cv32e40p-zedboard-project.tcl   # generates the Vivado project (used by Makefile)
├── Makefile                        # create and delete the Vivado project
├── Readme.md
├── sw
└── zedboard-wrapper                # zedboard specific design (.sv) and constraints (.xdc) files, used by the Vivado project
```

### Project Purpose
The purpose of this project is to compare the original CPU design and a modified one in the following aspects:

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