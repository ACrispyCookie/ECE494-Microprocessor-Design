# MUL dependency matrix for the no-MUL-forwarding variant.
# Covers immediate consumers on rs1, rs2, both operands, store data, and branch
# operands. The expected behavior is one-cycle stalling then WB forwarding.
#include "test_macros.S"

.section .text
.global _start
_start:
    li s0, DMEM_BASE

    # MUL -> ALU rs1.
    li t0, 37
    li t1, -11
    mul t2, t0, t1
    addi t3, t2, 5
    WRITE_SIG 0, t3

    # MUL -> ALU rs2.
    li t4, 1000
    li t5, 6
    li t6, 7
    mul a0, t5, t6
    sub a1, t4, a0
    WRITE_SIG 1, a1

    # MUL -> both source operands.
    li a2, 9
    li a3, 9
    mul a4, a2, a3
    add a5, a4, a4
    WRITE_SIG 2, a5

    # MUL -> store data.
    li a6, 12
    li a7, -12
    mul s1, a6, a7
    sw s1, 12(s0)

    # MUL -> branch operand: product equals 63, branch should take.
    li t0, 9
    li t1, 7
    mul t2, t0, t1
    li t3, 63
    beq t2, t3, mul_branch_taken
    li t4, 0xbad00001
    WRITE_SIG 4, t4
    j after_mul_branch
mul_branch_taken:
    li t4, 0x600d0001
    WRITE_SIG 4, t4
after_mul_branch:

    # Back-to-back MUL producers with immediate consumer of the youngest value.
    li t5, 2
    li t6, 3
    mul a0, t5, t6
    li t5, 4
    li t6, 5
    mul a0, t5, t6
    addi a1, a0, 1
    WRITE_SIG 5, a1

    TEST_DONE
