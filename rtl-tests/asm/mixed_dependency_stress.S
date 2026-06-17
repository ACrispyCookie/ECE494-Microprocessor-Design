# Mixed long dependency stress test.
# Exercises ALU, MUL, load, store, branch, and forwarding priority in one compact
# program with no inserted NOPs.
#include "test_macros.S"

.section .text
.global _start
_start:
    li s0, DMEM_BASE

    li t0, 3
    li t1, 4
    add t2, t0, t1
    mul t3, t2, t1
    addi t4, t3, 2
    sw t4, 64(s0)
    lw t5, 64(s0)
    xor t6, t5, t4
    WRITE_SIG 0, t6

    # Same destination rewritten by mixed producer classes; consumer must see newest.
    li a0, 5
    addi a0, a0, 1
    mul a0, a0, t1
    addi a1, a0, 7
    WRITE_SIG 1, a1

    # Branch on a just-loaded value that came from a just-stored MUL consumer.
    sw a1, 68(s0)
    lw a2, 68(s0)
    li a3, 31
    beq a2, a3, mixed_branch_taken
    li a4, 0xbad00001
    WRITE_SIG 2, a4
    j after_mixed_branch
mixed_branch_taken:
    li a4, 0x1234abcd
    WRITE_SIG 2, a4
after_mixed_branch:

    # Address dependency after arithmetic chain.
    addi a5, s0, 72
    addi a6, a5, 0
    li a7, 0x76543210
    sw a7, 0(a6)
    lw s1, 72(s0)
    WRITE_SIG 3, s1

    TEST_DONE
