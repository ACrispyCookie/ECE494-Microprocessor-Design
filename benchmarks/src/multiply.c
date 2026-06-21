#include "bench.h"
#define N 160
static int out[N];

int main(void) {
    bench_start();
    int acc = 7;
    for (int i = 0; i < N; i++) {
        int x = i + 3;
        int y = (i & 7) + 5;
        acc = acc + x * y;
        out[i] = acc * (y - 2);
    }
    bench_stop();
    uint32_t sig = (uint32_t)acc;
    for (int i = 0; i < N; i++) sig ^= (uint32_t)out[i] + (sig << 3);
    bench_signature(sig);
    return sig == 0 ? 1 : 0;
}
