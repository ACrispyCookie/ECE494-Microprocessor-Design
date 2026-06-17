# Branch operand dependency matrix.
# Every branch consumes a just-produced operand and writes an independent
# signature so wrong taken/not-taken behavior is easy to localize.
#include "test_macros.S"

.section .text
.global _start
_start:
    li s0, DMEM_BASE

    # BEQ with immediately-produced equal operand: should take.
    li t0, 21
    addi t1, t0, 0
    beq t1, t0, beq_taken
    li t2, 0xbad00001
    WRITE_SIG 0, t2
    j after_beq
beq_taken:
    li t2, 0xaaa00001
    WRITE_SIG 0, t2
after_beq:

    # BNE with immediately-produced different operand: should take.
    addi t3, t0, 1
    bne t3, t0, bne_taken
    li t4, 0xbad00002
    WRITE_SIG 1, t4
    j after_bne
bne_taken:
    li t4, 0xaaa00002
    WRITE_SIG 1, t4
after_bne:

    # BLT signed after producer: -3 < 2 should take.
    li t5, -3
    addi t6, t5, 0
    li a0, 2
    blt t6, a0, blt_taken
    li a1, 0xbad00003
    WRITE_SIG 2, a1
    j after_blt
blt_taken:
    li a1, 0xaaa00003
    WRITE_SIG 2, a1
after_blt:

    # BGE signed after producer: 5 >= -1 should take.
    li a2, 4
    addi a2, a2, 1
    li a3, -1
    bge a2, a3, bge_taken
    li a4, 0xbad00004
    WRITE_SIG 3, a4
    j after_bge
bge_taken:
    li a4, 0xaaa00004
    WRITE_SIG 3, a4
after_bge:

    # BLTU unsigned after producer: 1 < 0xffffffff should take.
    li a5, 0
    addi a5, a5, 1
    li a6, -1
    bltu a5, a6, bltu_taken
    li a7, 0xbad00005
    WRITE_SIG 4, a7
    j after_bltu
bltu_taken:
    li a7, 0xaaa00005
    WRITE_SIG 4, a7
after_bltu:

    # BGEU unsigned after producer: 0xffffffff >= 1 should take.
    li s1, -2
    addi s1, s1, 1
    li t0, 1
    bgeu s1, t0, bgeu_taken
    li t1, 0xbad00006
    WRITE_SIG 5, t1
    j after_bgeu
bgeu_taken:
    li t1, 0xaaa00006
    WRITE_SIG 5, t1
after_bgeu:

    TEST_DONE
