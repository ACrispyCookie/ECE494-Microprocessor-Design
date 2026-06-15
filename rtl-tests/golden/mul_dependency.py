def expected():
    def u32(x):
        return x & 0xFFFFFFFF

    first_mul = 37 * -11
    second_mul = 0x00010001 * 0x00000003
    return [
        u32(first_mul),
        u32(first_mul + 5),
        u32(second_mul),
        u32(second_mul ^ 0x00010001),
    ]
