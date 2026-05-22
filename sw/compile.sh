#!/usr/bin/env bash
set -euo pipefail

TOOLCHAIN_PREFIX=riscv64-unknown-elf

SRC="smoke_test/smoke.S"
LINKER="smoke_test/linker.ld"
ELF="smoke_test/smoke.elf"
DUMP="smoke_test/smoke.dump"
MEM="../cv32e40p-vivado-zedboard.srcs/sources_1/new/program_imem.mem"

${TOOLCHAIN_PREFIX}-gcc \
  -march=rv32im \
  -mabi=ilp32 \
  -nostdlib \
  -nostartfiles \
  -Wl,--no-relax \
  -T "${LINKER}" \
  "${SRC}" \
  -o "${ELF}"

${TOOLCHAIN_PREFIX}-objdump \
  -d \
  -M no-aliases,numeric \
  "${ELF}" > "${DUMP}"

${TOOLCHAIN_PREFIX}-objcopy \
  -O verilog \
  "${ELF}" \
  "${MEM}"

echo "Built ${ELF}"
echo "Wrote disassembly to ${DUMP}"
echo "Wrote memory image to ${MEM}"

