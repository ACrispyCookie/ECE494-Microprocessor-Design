def expected():
    return [
        sum(range(5)) & 0xFFFFFFFF,
        0x11111111,
        0x33333333,
        0xABCDEF01,
        0xABCDEF01,
    ]
