/* Explicit request accounting; instrumentation headers and libc-internal work are excluded. */
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>

static int ail_resource_stage = 6;
static size_t live, live_bytes, peak_bytes;
static uint64_t resource_alloc_calls[7], resource_alloc_bytes[7];
static uint64_t resource_realloc_calls[7], resource_realloc_bytes[7];
static uint64_t resource_copy_calls[7], resource_copy_bytes[7];
static uint64_t resource_fill_bytes[7], resource_zero_bytes[7], resource_stage_peak[7];
typedef union { max_align_t alignment; size_t size; } ail_resource_header;

static unsigned resource_stage(void) {
    if (ail_resource_stage < 0 || ail_resource_stage >= 7) exit(91);
    return (unsigned)ail_resource_stage;
}
static void resource_add(uint64_t *counter, uintmax_t amount) {
    if (amount > UINT64_MAX || *counter > UINT64_MAX - (uint64_t)amount) exit(91);
    *counter += (uint64_t)amount;
}
static void resource_peak(unsigned stage) {
    if (live_bytes > peak_bytes) peak_bytes = live_bytes;
    if ((uintmax_t)live_bytes > UINT64_MAX) exit(91);
    if ((uint64_t)live_bytes > resource_stage_peak[stage]) resource_stage_peak[stage] = (uint64_t)live_bytes;
}
static void *resource_allocate(size_t size, int zero, unsigned stage) {
    if (size > SIZE_MAX - sizeof(ail_resource_header)) return NULL;
    ail_resource_header *header = zero ? calloc(1, sizeof *header + size) : malloc(sizeof *header + size);
    if (!header) return NULL;
    if (live == SIZE_MAX || size > SIZE_MAX - live_bytes) exit(91);
    header->size = size;
    ++live; live_bytes += size;
    resource_add(&resource_alloc_calls[stage], 1);
    resource_add(&resource_alloc_bytes[stage], size);
    if (zero) resource_add(&resource_zero_bytes[stage], size);
    resource_peak(stage);
    return header + 1;
}
static void *resource_malloc(size_t size) {
    return resource_allocate(size, 0, resource_stage());
}
static void *resource_calloc(size_t count, size_t size) {
    unsigned stage = resource_stage();
    if (size && count > SIZE_MAX / size) return NULL;
    return resource_allocate(count * size, 1, stage);
}
static void resource_free(void *pointer) {
    (void)resource_stage();
    if (!pointer) return;
    ail_resource_header *header = (ail_resource_header *)pointer - 1;
    if (!live || header->size > live_bytes) exit(91);
    --live; live_bytes -= header->size;
    free(header);
}
static void *resource_realloc(void *pointer, size_t size) {
    unsigned stage = resource_stage();
    if (!pointer) {
        void *result = resource_allocate(size, 0, stage);
        if (result) {
            resource_add(&resource_realloc_calls[stage], 1);
            resource_add(&resource_realloc_bytes[stage], size);
        }
        return result;
    }
    if (!size) {
        resource_free(pointer);
        resource_add(&resource_alloc_calls[stage], 1);
        resource_add(&resource_realloc_calls[stage], 1);
        return NULL;
    }
    if (size > SIZE_MAX - sizeof(ail_resource_header)) return NULL;
    ail_resource_header *old = (ail_resource_header *)pointer - 1;
    size_t previous = old->size;
    if (!live || previous > live_bytes || size > SIZE_MAX - (live_bytes - previous)) exit(91);
    ail_resource_header *next = realloc(old, sizeof *next + size);
    if (!next) return NULL;
    next->size = size;
    live_bytes = live_bytes - previous + size;
    resource_add(&resource_alloc_calls[stage], 1);
    resource_add(&resource_alloc_bytes[stage], size);
    resource_add(&resource_realloc_calls[stage], 1);
    resource_add(&resource_realloc_bytes[stage], size);
    resource_peak(stage);
    return next + 1;
}
static void resource_copy(size_t bytes) {
    unsigned stage = resource_stage();
    resource_add(&resource_copy_calls[stage], 1);
    resource_add(&resource_copy_bytes[stage], bytes);
}
static void *resource_memcpy(void *destination, const void *source, size_t bytes) {
    resource_copy(bytes);
    return memcpy(destination, source, bytes);
}
static void *resource_memmove(void *destination, const void *source, size_t bytes) {
    resource_copy(bytes);
    return memmove(destination, source, bytes);
}
static void *resource_memset(void *destination, int value, size_t bytes) {
    unsigned stage = resource_stage();
    resource_add(&resource_fill_bytes[stage], bytes);
    if ((unsigned char)value == 0) resource_add(&resource_zero_bytes[stage], bytes);
    return memset(destination, value, bytes);
}
#define malloc resource_malloc
#define calloc resource_calloc
#define realloc resource_realloc
#define free resource_free
#define memcpy resource_memcpy
#define memmove resource_memmove
#define memset resource_memset
