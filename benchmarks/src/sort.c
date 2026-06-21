#include "bench.h"
#define N 128
static int data[N];

static void init_data(void) {
    uint32_t x = 0xdeadbeefu;
    for (int i = 0; i < N; i++) {
        x ^= x << 13; x ^= x >> 17; x ^= x << 5;
        data[i] = (int)(x & 0x7ffu);
    }
}

static void quicksort(int lo, int hi) {
    int i = lo, j = hi;
    int pivot = data[(lo + hi) >> 1];
    while (i <= j) {
        while (data[i] < pivot) i++;
        while (data[j] > pivot) j--;
        if (i <= j) {
            int t = data[i]; data[i] = data[j]; data[j] = t;
            i++; j--;
        }
    }
    if (lo < j) quicksort(lo, j);
    if (i < hi) quicksort(i, hi);
}

int main(void) {
    init_data();
    bench_start();
    quicksort(0, N - 1);
    bench_stop();
    uint32_t sig = 0x9e3779b9u;
    for (int i = 0; i < N; i++) sig = (sig << 7) ^ (sig >> 3) ^ (uint32_t)data[i];
    bench_signature(sig);
    for (int i = 1; i < N; i++) if (data[i - 1] > data[i]) return 1;
    return 0;
}
