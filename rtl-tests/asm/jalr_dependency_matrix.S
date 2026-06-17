# JAL/JALR dependency matrix.
# Covers immediate use of link registers and ALU-produced JALR target registers.
#include "test_macros.S"

.section .text
.global _start
_start:
    li s0, DMEM_BASE

    # JAL writes ra; target immediately uses ra in JALR to return.
    jal ra, return_immediately
    li t0, 0x11110001
    WRITE_SIG 0, t0
    j after_return_immediately
return_immediately:
    jalr zero, 0(ra)
after_return_immediately:

    # ALU-produced JALR target register consumed immediately by JALR.
    la t1, indirect_target
    addi t2, t1, 0
    jalr ra, 0(t2)
    li t3, 0x22220002
    WRITE_SIG 2, t3
    j after_indirect
indirect_target:
    li t4, 0x22220001
    WRITE_SIG 1, t4
    jalr zero, 0(ra)
after_indirect:

    # JAL link consumed as a normal ALU operand after return.
    jal ra, link_consumer_target
link_consumer_return:
    addi a0, ra, 4
    WRITE_SIG 4, a0
    TEST_DONE
link_consumer_target:
    li a1, 0x33330003
    WRITE_SIG 3, a1
    jalr zero, 0(ra)
