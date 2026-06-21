#include "bench.h"
#define N 12
static int a[N][N], b[N][N], c[N][N];

int main(void) {
    for (int i = 0; i < N; i++) for (int j = 0; j < N; j++) {
        a[i][j] = (i * 3 + j + 1) & 15;
        b[i][j] = (i + j * 5 + 2) & 15;
        c[i][j] = 0;
    }
    bench_start();
    for (int i = 0; i < N; i++)
        for (int j = 0; j < N; j++) {
            int sum = 0;
            for (int k = 0; k < N; k++) sum += a[i][k] * b[k][j];
            c[i][j] = sum;
        }
    bench_stop();
    uint32_t sig = 0;
    for (int i = 0; i < N; i++) for (int j = 0; j < N; j++) sig = sig * 31u + (uint32_t)c[i][j];
    bench_signature(sig);
    return sig == 0 ? 1 : 0;
}
