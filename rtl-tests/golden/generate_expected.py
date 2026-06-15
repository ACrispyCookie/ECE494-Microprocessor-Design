#!/usr/bin/env python3
"""Generate expected CV32E40P DMEM and regfile dumps from assembly.

This is intentionally similar to the ECE338 test flow: a Python reference
program consumes the assembled program/disassembly and emits file-based golden
memories (`expected_dmem.mem` and `expected_regfile.mem`) that the RTL testbench
can load and compare against the hardware final state.
"""
from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

DMEM_WORDS = 4096
REGS = 32
DONE_ADDR = 0x0001_FFFC
DONE_MAGIC = 0x5555_AAAA

REG_ALIASES = {
    "zero": 0,
    "ra": 1,
    "sp": 2,
    "gp": 3,
    "tp": 4,
    "t0": 5,
    "t1": 6,
    "t2": 7,
    "s0": 8,
    "fp": 8,
    "s1": 9,
    "a0": 10,
    "a1": 11,
    "a2": 12,
    "a3": 13,
    "a4": 14,
    "a5": 15,
    "a6": 16,
    "a7": 17,
    "s2": 18,
    "s3": 19,
    "s4": 20,
    "s5": 21,
    "s6": 22,
    "s7": 23,
    "s8": 24,
    "s9": 25,
    "s10": 26,
    "s11": 27,
    "t3": 28,
    "t4": 29,
    "t5": 30,
    "t6": 31,
}
for i in range(32):
    REG_ALIASES[f"x{i}"] = i


def u32(value: int) -> int:
    return value & 0xFFFF_FFFF


def s32(value: int) -> int:
    value &= 0xFFFF_FFFF
    return value - 0x1_0000_0000 if value & 0x8000_0000 else value


def reg(token: str) -> int:
    token = token.strip()
    if token not in REG_ALIASES:
        raise ValueError(f"Unknown register: {token}")
    return REG_ALIASES[token]


def imm(token: str) -> int:
    token = token.strip()
    return int(token, 0)


def objdump_addr(token: str) -> int:
    """Parse objdump bare target addresses, which are hexadecimal without 0x."""
    token = token.strip()
    sign = -1 if token.startswith("-") else 1
    token = token[1:] if token[0:1] in "+-" else token
    return sign * int(token, 16)


def parse_mem_operand(token: str) -> tuple[int, int]:
    match = re.fullmatch(r"([+-]?(?:0x[0-9a-fA-F]+|[0-9a-fA-F]+))\(([^)]+)\)", token.strip())
    if not match:
        raise ValueError(f"Invalid memory operand: {token}")
    return imm(match.group(1)), reg(match.group(2))


def split_operands(text: str) -> list[str]:
    return [part.strip() for part in text.split(",") if part.strip()]


def disassemble(objdump: str, elf: Path) -> list[tuple[int, str, list[str]]]:
    proc = subprocess.run(
        [objdump, "-d", "-M", "numeric,no-aliases", str(elf)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=True,
    )
    program: list[tuple[int, str, list[str]]] = []
    pattern = re.compile(r"^\s*([0-9a-fA-F]+):\s+[0-9a-fA-F]+\s+([a-zA-Z0-9_.]+)\s*(.*)$")
    for line in proc.stdout.splitlines():
        match = pattern.match(line)
        if not match:
            continue
        pc = int(match.group(1), 16)
        op = match.group(2).lower()
        operands = split_operands(match.group(3).split("#", 1)[0].strip())
        program.append((pc, op, operands))
    if not program:
        raise RuntimeError(f"No instructions found in objdump for {elf}")
    return program


def generate(elf: Path, objdump: str, max_instructions: int = 10000) -> tuple[list[int], list[int]]:
    program = disassemble(objdump, elf)
    pc_to_index = {pc: idx for idx, (pc, _, _) in enumerate(program)}
    regs = [0] * REGS
    dmem = [0] * DMEM_WORDS
    pc = 0
    executed = 0

    def write_reg(rd: int, value: int) -> None:
        if rd != 0:
            regs[rd] = u32(value)

    while executed < max_instructions:
        if pc not in pc_to_index:
            raise RuntimeError(f"PC 0x{pc:08x} left the disassembled program")
        idx = pc_to_index[pc]
        cur_pc, op, ops = program[idx]
        next_pc = cur_pc + 4
        executed += 1

        if op == "nop":
            pass
        elif op in {"add", "sub", "mul", "and", "or", "xor", "sll", "srl", "sra", "slt", "sltu"}:
            rd, rs1, rs2 = reg(ops[0]), reg(ops[1]), reg(ops[2])
            a, b = regs[rs1], regs[rs2]
            if op == "add":
                value = a + b
            elif op == "sub":
                value = a - b
            elif op == "mul":
                value = a * b
            elif op == "and":
                value = a & b
            elif op == "or":
                value = a | b
            elif op == "xor":
                value = a ^ b
            elif op == "sll":
                value = a << (b & 0x1F)
            elif op == "srl":
                value = a >> (b & 0x1F)
            elif op == "sra":
                value = s32(a) >> (b & 0x1F)
            elif op == "slt":
                value = 1 if s32(a) < s32(b) else 0
            else:  # sltu
                value = 1 if a < b else 0
            write_reg(rd, value)
        elif op in {"addi", "andi", "ori", "xori", "slli", "srli", "srai", "slti", "sltiu"}:
            rd, rs1, im = reg(ops[0]), reg(ops[1]), imm(ops[2])
            a = regs[rs1]
            if op == "addi":
                value = a + im
            elif op == "andi":
                value = a & im
            elif op == "ori":
                value = a | im
            elif op == "xori":
                value = a ^ im
            elif op == "slli":
                value = a << (im & 0x1F)
            elif op == "srli":
                value = a >> (im & 0x1F)
            elif op == "srai":
                value = s32(a) >> (im & 0x1F)
            elif op == "slti":
                value = 1 if s32(a) < im else 0
            else:  # sltiu
                value = 1 if a < u32(im) else 0
            write_reg(rd, value)
        elif op == "lui":
            write_reg(reg(ops[0]), imm(ops[1]) << 12)
        elif op == "auipc":
            write_reg(reg(ops[0]), cur_pc + (imm(ops[1]) << 12))
        elif op == "lw":
            rd = reg(ops[0])
            off, base = parse_mem_operand(ops[1])
            addr = u32(regs[base] + off)
            write_reg(rd, dmem[(addr >> 2) % DMEM_WORDS])
        elif op == "sw":
            rs2 = reg(ops[0])
            off, base = parse_mem_operand(ops[1])
            addr = u32(regs[base] + off)
            dmem[(addr >> 2) % DMEM_WORDS] = regs[rs2]
            if addr == DONE_ADDR and regs[rs2] == DONE_MAGIC:
                regs[0] = 0
                return regs, dmem
        elif op in {"beq", "bne", "blt", "bge", "bltu", "bgeu"}:
            rs1, rs2 = reg(ops[0]), reg(ops[1])
            a, b = regs[rs1], regs[rs2]
            take = (
                (op == "beq" and a == b)
                or (op == "bne" and a != b)
                or (op == "blt" and s32(a) < s32(b))
                or (op == "bge" and s32(a) >= s32(b))
                or (op == "bltu" and a < b)
                or (op == "bgeu" and a >= b)
            )
            if take:
                next_pc = objdump_addr(ops[2].split()[0])
        elif op == "jal":
            rd = reg(ops[0])
            write_reg(rd, cur_pc + 4)
            next_pc = objdump_addr(ops[1].split()[0])
        elif op == "jalr":
            rd = reg(ops[0])
            off, base = parse_mem_operand(ops[1]) if "(" in ops[1] else (imm(ops[2]), reg(ops[1]))
            target = u32(regs[base] + off) & ~1
            write_reg(rd, cur_pc + 4)
            next_pc = target
        else:
            raise NotImplementedError(f"Unsupported instruction at 0x{cur_pc:08x}: {op} {', '.join(ops)}")

        regs[0] = 0
        pc = next_pc

    raise RuntimeError(f"Golden model exceeded max_instructions={max_instructions}; probable infinite loop before DONE")


def write_mem(path: Path, values: list[int]) -> None:
    path.write_text("".join(f"{u32(v):08x}\n" for v in values))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", required=True, type=Path)
    parser.add_argument("--objdump", default="riscv-none-elf-objdump")
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--max-instructions", type=int, default=10000)
    args = parser.parse_args()

    regs, dmem = generate(args.elf, args.objdump, args.max_instructions)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_mem(args.out_dir / "expected_regfile.mem", regs)
    write_mem(args.out_dir / "expected_dmem.mem", dmem)
    print(f"[GOLDEN] Wrote {args.out_dir / 'expected_regfile.mem'}")
    print(f"[GOLDEN] Wrote {args.out_dir / 'expected_dmem.mem'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
