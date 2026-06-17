# ALU forwarding/dependency matrix.
# Covers immediate consumers on rs1, rs2, both operands, self-overwrite, and
# youngest-result priority when the same destination is written in consecutive cycles.
#include "test_macros.S"

.section .text
.global _start
_start:
    li s0, DMEM_BASE

    # rs1 dependency: add -> addi consumes rd as rs1 immediately.
    li t0, 10
    li t1, 7
    add t2, t0, t1
    addi t3, t2, 5
    WRITE_SIG 0, t3

    # rs2 dependency: add -> sub consumes rd as rs2 immediately.
    li t4, 100
    add t5, t0, t1
    sub t6, t4, t5
    WRITE_SIG 1, t6

    # Both operands from the immediately previous result.
    add a0, t0, t1
    add a1, a0, a0
    WRITE_SIG 2, a1

    # Self-overwrite dependency chain.
    li a2, 1
    addi a2, a2, 2
    addi a2, a2, 3
    addi a2, a2, 4
    WRITE_SIG 3, a2

    # Youngest-result forwarding priority for same rd.
    li a3, 5
    addi a3, a3, 10
    addi a3, a3, 20
    addi a4, a3, 30
    WRITE_SIG 4, a4

    # Shift and compare consumers.
    li a5, 0x80
    slli a5, a5, 3
    srli a6, a5, 4
    sltiu a7, a6, 0x100
    WRITE_SIG 5, a5
    WRITE_SIG 6, a6
    WRITE_SIG 7, a7

    # x0 dependency should not create a false value or false stall result.
    addi zero, a4, 123
    addi s1, zero, 9
    WRITE_SIG 8, s1

    TEST_DONE
