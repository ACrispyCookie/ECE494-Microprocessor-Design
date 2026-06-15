# Basic ALU/load-store signature test.
#include "test_macros.S"

.section .text
.global _start
_start:
    li s0, DMEM_BASE

    li t0, 0x12345678
    li t1, 0x00000f0f
    add t2, t0, t1
    WRITE_SIG 0, t2

    sub t3, t0, t1
    WRITE_SIG 1, t3

    xor t4, t0, t1
    WRITE_SIG 2, t4

    or t5, t0, t1
    WRITE_SIG 3, t5

    and t6, t0, t1
    WRITE_SIG 4, t6

    slli t2, t1, 4
    WRITE_SIG 5, t2

    srli t3, t0, 8
    WRITE_SIG 6, t3

    srai t4, t0, 4
    WRITE_SIG 7, t4

    lw a0, 0(s0)
    addi a0, a0, 1
    WRITE_SIG 8, a0

    TEST_DONE
