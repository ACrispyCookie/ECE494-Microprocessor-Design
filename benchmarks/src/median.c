#include "bench.h"
#define N 101
static int data[N];

static void init_data(void) {
    uint32_t x = 0x1234567u;
    for (int i = 0; i < N; i++) {
        x = x * 1664525u + 1013904223u;
        data[i] = (int)(x & 0x3ffu);
    }
}

int main(void) {
    init_data();
    bench_start();
    for (int i = 1; i < N; i++) {
        int key = data[i];
        int j = i - 1;
        while (j >= 0 && data[j] > key) {
            data[j + 1] = data[j];
            j--;
        }
        data[j + 1] = key;
    }
    int med = data[N / 2];
    bench_stop();
    uint32_t sig = (uint32_t)med;
    for (int i = 0; i < N; i++) sig = sig * 33u + (uint32_t)data[i];
    bench_signature(sig);
    for (int i = 1; i < N; i++) if (data[i - 1] > data[i]) return 1;
    return med < 0 ? 2 : 0;
}
