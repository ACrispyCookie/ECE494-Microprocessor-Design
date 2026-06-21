#ifndef ECE494_BENCH_H
#define ECE494_BENCH_H

#include <stdint.h>
#include <stddef.h>

#define BENCH_RESULT_ADDR 0x00010000u
#define BENCH_SIGNATURE_ADDR 0x00010004u
#define BENCH_START_ADDR 0x0001fff0u
#define BENCH_STOP_ADDR 0x0001fff4u
#define BENCH_DONE_ADDR 0x0001fffcu
#define BENCH_DONE_MAGIC 0x5555aaaau

static inline void bench_mmio_write(uint32_t addr, uint32_t value) {
    *(volatile uint32_t *)addr = value;
}

static inline void bench_start(void) {
    bench_mmio_write(BENCH_START_ADDR, 0x1u);
}

static inline void bench_stop(void) {
    bench_mmio_write(BENCH_STOP_ADDR, 0x1u);
}

static inline void bench_signature(uint32_t value) {
    bench_mmio_write(BENCH_SIGNATURE_ADDR, value);
}

void *memcpy(void *dst, const void *src, size_t n);
void *memset(void *dst, int c, size_t n);
char *strcpy(char *dst, const char *src);
int strcmp(const char *a, const char *b);
size_t strlen(const char *s);

#endif
