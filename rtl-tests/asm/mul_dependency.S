# Multiply dependency test.  The instruction immediately after MUL consumes
# the result, so this catches missing stall/forwarding behavior around MUL.
#include "test_macros.S"

.section .text
.global _start
_start:
    li s0, DMEM_BASE

    li t0, 37
    li t1, -11
    mul t2, t0, t1
    addi t3, t2, 5
    WRITE_SIG 0, t2
    WRITE_SIG 1, t3

    li t4, 0x00010001
    li t5, 0x00000003
    mul t6, t4, t5
    xor a0, t6, t4
    WRITE_SIG 2, t6
    WRITE_SIG 3, a0

    TEST_DONE
