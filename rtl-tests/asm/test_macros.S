# Common addresses used by rtl-tests/tb/tb_cv32e40p_rtl.sv.
.equ DMEM_BASE, 0x00010000
.equ DONE_ADDR, 0x0001fffc
.equ DONE_MAGIC, 0x5555aaaa

.macro WRITE_SIG word_index, src_reg
    sw \src_reg, (\word_index * 4)(s0)
.endm

.macro TEST_DONE
    li t6, DONE_ADDR
    li t5, DONE_MAGIC
    sw t5, 0(t6)
1:  j 1b
.endm
