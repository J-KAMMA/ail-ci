/* Counting allocator for the bare-metal RAM table (`-Wl,--wrap=malloc` etc.).

   Tracks the current and peak bytes handed out by the AIL runtime. newlib-nano
   provides malloc_usable_size(), so free() can subtract the real block size.
   memcount_peak() is read by startup.c after main() and printed to stderr,
   which keeps stdout identical to CPython. */
#include <malloc.h>
#include <stddef.h>

void *__real_malloc(size_t n);
void *__real_calloc(size_t n, size_t m);
void *__real_realloc(void *p, size_t n);
void __real_free(void *p);

static size_t used, peak;

size_t memcount_used(void) { return used; }
size_t memcount_peak(void) { return peak; }

static void add(size_t n) {
    used += n;
    if (used > peak) peak = used;
}

void *__wrap_malloc(size_t n) {
    void *p = __real_malloc(n);
    if (p) add(malloc_usable_size(p));
    return p;
}

void *__wrap_calloc(size_t n, size_t m) {
    void *p = __real_calloc(n, m);
    if (p) add(malloc_usable_size(p));
    return p;
}

void *__wrap_realloc(void *p, size_t n) {
    if (p) used -= malloc_usable_size(p);
    void *q = __real_realloc(p, n);
    if (q) add(malloc_usable_size(q));
    return q;
}

void __wrap_free(void *p) {
    if (p) {
        size_t n = malloc_usable_size(p);
        if (n <= used) used -= n; else used = 0;
    }
    __real_free(p);
}
