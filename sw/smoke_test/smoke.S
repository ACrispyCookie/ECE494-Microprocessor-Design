.section .text
.global _start

.option norvc

_start:
    lui  x1, 0x00010        # x1 = 0x00010000, base of DMEM
    lui  x2, 0x12345        # x2 = 0x12345000
    addi x2, x2, 0x678      # x2 = 0x12345678
    sw   x2, 0(x1)          # DMEM[0] = 0x12345678

loop:
    jal  x0, loop
