# CV32E40P RTL assembly tests (Icarus Verilog)

This directory contains a fully automated RTL regression flow for both local CV32E40P versions:

- `baseline` -> `cv32e40p_baseline`
- `no_mul_forwarding` -> `cv32e40p_no_mul_forwarding`

The flow uses assembly files as instruction memory, runs the CPU in RTL with `iverilog`/`vvp`, dumps the data-memory signature, and compares it against a Python golden model.

## Layout

- `asm/*.S` — assembly tests. Each test writes signature words at `DMEM_BASE` (`0x00010000`) and finishes by storing `DONE_MAGIC` to `DONE_ADDR`.
- `asm/test_macros.S` — common assembly constants/macros.
- `golden/*.py` — Python golden models. Each file must define `expected()` and return the expected signature words.
- `tb/tb_cv32e40p_rtl.sv` — generic RTL testbench.
- `../scripts/run-rtl-tests.py` — build/run/compare driver.

## Run

From the repository root:

```bash
make rtl-tests
```

Useful focused runs:

```bash
make rtl-tests-baseline
make rtl-tests-no-mul-forwarding
python3 scripts/run-rtl-tests.py --version baseline --test alu_load_store
python3 scripts/run-rtl-tests.py --force-rebuild
```

If `sv2v` is not already installed, the runner downloads the pinned Linux release under `build/tools/`. This is needed because Icarus Verilog cannot parse several SystemVerilog constructs used directly by CV32E40P; the simulation itself is still compiled and run by `iverilog`/`vvp`.

## Adding a test

1. Add `rtl-tests/asm/<name>.S`.
2. Include `test_macros.S`.
3. Write expected signature words to `DMEM_BASE` using `WRITE_SIG`.
4. Finish with `TEST_DONE`.
5. Add `rtl-tests/golden/<name>.py` with:

```python
def expected():
    return [0x12345678]
```

Then run:

```bash
python3 scripts/run-rtl-tests.py --test <name>
```

The per-test artifacts are written under `build/rtl-tests/<version>/<test>/`, including `program_imem.mem`, `dmem_dump.mem`, and `sim.log`.
