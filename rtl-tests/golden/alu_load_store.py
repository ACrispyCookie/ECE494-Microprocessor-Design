def expected():
    t0 = 0x12345678
    t1 = 0x00000F0F
    return [
        (t0 + t1) & 0xFFFFFFFF,
        (t0 - t1) & 0xFFFFFFFF,
        t0 ^ t1,
        t0 | t1,
        t0 & t1,
        (t1 << 4) & 0xFFFFFFFF,
        (t0 >> 8) & 0xFFFFFFFF,
        (t0 >> 4) & 0xFFFFFFFF,  # srai is same as srli for this positive value
        ((t0 + t1) + 1) & 0xFFFFFFFF,
    ]
