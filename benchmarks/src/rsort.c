#include "bench.h"
#define N 256
static uint32_t data[N];
static uint32_t tmp[N];

static void init_data(void) {
    uint32_t x = 1u;
    for (int i = 0; i < N; i++) {
        x = x * 1103515245u + 12345u;
        data[i] = x & 0xffffu;
    }
}

int main(void) {
    init_data();
    bench_start();
    for (int shift = 0; shift < 16; shift += 8) {
        int count[256];
        for (int i = 0; i < 256; i++) count[i] = 0;
        for (int i = 0; i < N; i++) count[(data[i] >> shift) & 0xffu]++;
        int sum = 0;
        for (int i = 0; i < 256; i++) { int c = count[i]; count[i] = sum; sum += c; }
        for (int i = 0; i < N; i++) tmp[count[(data[i] >> shift) & 0xffu]++] = data[i];
        for (int i = 0; i < N; i++) data[i] = tmp[i];
    }
    bench_stop();
    uint32_t sig = 0;
    for (int i = 0; i < N; i++) sig = sig * 17u + data[i];
    bench_signature(sig);
    for (int i = 1; i < N; i++) if (data[i - 1] > data[i]) return 1;
    return 0;
}
