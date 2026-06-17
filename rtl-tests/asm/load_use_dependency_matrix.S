# Load-use dependency matrix.
# Covers immediate load consumers as ALU operands, store data, branch operands,
# and a dependent load address. No defensive NOPs are inserted.
#include "test_macros.S"

.section .text
.global _start
_start:
    li s0, DMEM_BASE

    # Seed data away from the signature words used for checks.
    li t0, 0x11112222
    sw t0, 64(s0)
    li t0, 0x33334444
    sw t0, 68(s0)
    li t0, 7
    sw t0, 72(s0)
    addi t1, s0, 80
    sw t1, 76(s0)
    li t0, 0x55667788
    sw t0, 80(s0)

    # Load -> ALU rs1.
    lw t2, 64(s0)
    addi t3, t2, 1
    WRITE_SIG 0, t3

    # Load -> ALU rs2.
    li t4, 0x55555555
    lw t5, 68(s0)
    xor t6, t4, t5
    WRITE_SIG 1, t6

    # Load -> store data.
    lw a0, 64(s0)
    sw a0, 8(s0)

    # Load -> branch operand, taken path.
    lw a1, 72(s0)
    li a2, 7
    beq a1, a2, load_branch_taken
    li a3, 0xdead0001
    WRITE_SIG 2, a3
    j after_load_branch
load_branch_taken:
    li a3, 0xbeef0001
    WRITE_SIG 2, a3
after_load_branch:

    # Load -> dependent load address.
    lw a4, 76(s0)
    lw a5, 0(a4)
    WRITE_SIG 3, a5

    TEST_DONE
