# Store dependency matrix.
# Covers freshly-produced store data, freshly-produced store addresses, and
# store data after ALU/MUL/load producers.
#include "test_macros.S"

.section .text
.global _start
_start:
    li s0, DMEM_BASE

    # ALU -> store data.
    li t0, 0x1000
    addi t0, t0, 0x234
    sw t0, 0(s0)

    # ALU -> store address.
    li t1, 0xabcdef01
    addi t2, s0, 4
    sw t1, 0(t2)

    # MUL -> store data must wait/forward correctly.
    li t3, 13
    li t4, -9
    mul t5, t3, t4
    sw t5, 8(s0)

    # Load -> store data.
    lw t6, 0(s0)
    sw t6, 12(s0)

    # ALU-produced address followed by load to verify store landed there.
    addi a0, s0, 16
    li a1, 0x13572468
    sw a1, 0(a0)
    lw a2, 16(s0)
    WRITE_SIG 4, a2

    TEST_DONE
