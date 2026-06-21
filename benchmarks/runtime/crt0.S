.section .text.startup, "ax", @progbits
.globl _start
_start:
    la sp, __stack_top
    call main
    li t0, 0x00010000
    sw a0, 0(t0)
    li t0, 0x0001fffc
    li t1, 0x5555aaaa
    sw t1, 0(t0)
1:  j 1b
