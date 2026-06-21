#include "bench.h"
#define N 128
static int a[N], b[N], c[N];

int main(void) {
    for (int i = 0; i < N; i++) { a[i] = i * 3 + 1; b[i] = 1000 - i * 2; c[i] = 0; }
    bench_start();
    for (int i = 0; i < N; i++) c[i] = a[i] + b[i];
    bench_stop();
    uint32_t sig = 0;
    for (int i = 0; i < N; i++) sig = (sig << 5) ^ (sig >> 2) ^ (uint32_t)c[i];
    bench_signature(sig);
    for (int i = 0; i < N; i++) if (c[i] != 1001 + i) return 1;
    return 0;
}
