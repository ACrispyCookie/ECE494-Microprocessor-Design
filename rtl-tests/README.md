# CV32E40P RTL assembly tests (Icarus Verilog)

This directory contains a fully automated RTL regression flow for the local CV32E40P versions:

- `baseline` -> `cv32e40p_baseline`
- `no_mul_forwarding` -> `cv32e40p_no_mul_forwarding`
- `no_alu_forwarding` -> `cv32e40p_no_alu_forwarding`

The flow is file-based and mirrors the style of the `/workspace/ECE338-Parallel-Computer-Architecture/test` pipeline: assembly is compiled into an instruction-memory file, a Python reference program generates final-state golden dumps, and the RTL testbench loads those dumps and compares them against the CPU final state.

## Layout

- `asm/*.S` — assembly tests. Each test starts at `_start` and finishes by storing `DONE_MAGIC` to `DONE_ADDR` via `TEST_DONE`.
- `asm/test_macros.S` — common assembly constants/macros (`DMEM_BASE`, `DONE_ADDR`, `DONE_MAGIC`, `WRITE_SIG`, `TEST_DONE`).
- `golden/generate_expected.py` — Python reference simulator. It reads the assembled ELF disassembly and emits:
  - `expected_dmem.mem` — full expected 4096-word data memory dump.
  - `expected_regfile.mem` — expected 32-word integer register file dump.
- `tb/tb_cv32e40p_rtl.sv` — generic RTL testbench. It loads `program_imem.mem`, waits for the DONE store, dumps final DMEM/regfile, and compares them internally against the expected dumps.
- `../scripts/run-rtl-tests.py` — build/run driver.

## Run

From the repository root:

```bash
make rtl-tests
```

Useful focused runs:

```bash
make rtl-tests-baseline
make rtl-tests-no-mul-forwarding
make rtl-tests-no-alu-forwarding
python3 scripts/run-rtl-tests.py --version baseline --test alu_load_store
python3 scripts/run-rtl-tests.py --version no_alu_forwarding --test alu_load_store
python3 scripts/run-rtl-tests.py --force-rebuild
```

If `sv2v` is not already installed, the runner downloads the pinned Linux release under `build/tools/`. This is needed because Icarus Verilog cannot parse several SystemVerilog constructs used directly by CV32E40P; the simulation itself is still compiled and run by `iverilog`/`vvp`.

## Adding a test

1. Add `rtl-tests/asm/<name>.S`.
2. Include `test_macros.S`.
3. Use supported RV32IM instructions and/or assembler pseudos that expand to RV32IM.
4. Store any observable results in DMEM if desired (`WRITE_SIG <word_index>, <reg>` is a convenience macro).
5. Finish with `TEST_DONE` so the testbench knows when to stop.

Then run:

```bash
python3 scripts/run-rtl-tests.py --test <name>
```

No per-test `expected()` Python file is needed. The runner creates all per-test artifacts under `build/rtl-tests/<version>/<test>/`, including `program_imem.mem`, `expected_dmem.mem`, `expected_regfile.mem`, `dmem_dump.mem`, `regfile_dump.mem`, and `sim.log`.
