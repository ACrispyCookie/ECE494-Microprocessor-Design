.section .text
.global _start

.option norvc

_start:
    # Producer: exercise the M extension multiplier.
    addi x2, x0, 7
    addi x3, x0, 9
    mul  x4, x2, x3        # x4 = 63

    # Immediate consumer. This is the hazard the no-MUL-forwarding solution
    # must handle by stalling one cycle and then using WB forwarding.
    addi x5, x4, 5         # x5 = 68

    # Second dependent consumer to make sure the result is architecturally
    # written/forwarded, not only visible for one instruction.
    add  x6, x5, x4        # x6 = 131 = 0x83

    # Store to DMEM word 0.  Avoid using a separate base register so this smoke
    # test isolates the multiplier dependency path.
    sw   x6, 0(x0)

1:
    j 1b
