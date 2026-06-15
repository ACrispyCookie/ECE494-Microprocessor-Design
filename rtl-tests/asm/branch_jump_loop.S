# Branch/jump and loop signature test.
#include "test_macros.S"

.section .text
.global _start
_start:
    li s0, DMEM_BASE

    li t0, 0
    li t1, 5
    li t2, 0
loop_sum:
    add t2, t2, t0
    addi t0, t0, 1
    blt t0, t1, loop_sum
    WRITE_SIG 0, t2

    li t3, 0x11111111
    li t4, 0x22222222
    beq t3, t4, wrong_equal
    WRITE_SIG 1, t3
    j after_equal
wrong_equal:
    WRITE_SIG 1, t4
after_equal:

    li t5, -1
    li t6, 1
    bltu t5, t6, wrong_unsigned
    li a0, 0x33333333
    WRITE_SIG 2, a0
    j after_unsigned
wrong_unsigned:
    li a0, 0x44444444
    WRITE_SIG 2, a0
after_unsigned:

    jal ra, subroutine
    WRITE_SIG 4, a1

    TEST_DONE

subroutine:
    li a1, 0xabcdef01
    WRITE_SIG 3, a1
    jalr zero, 0(ra)
