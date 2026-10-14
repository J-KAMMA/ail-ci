"""Private C11 support emitted before the generated runtime's allocator macros."""

PRELUDE = r'''
#include <stdlib.h>
#include <stdint.h>
#include <stddef.h>
#include <errno.h>
#include <setjmp.h>
#include <stdatomic.h>
#include <stdio.h>
#include <string.h>
#ifdef _WIN32
#include <wchar.h>
#endif

static jmp_buf ail_api_jump;
static int ail_api_status;
static char ail_api_message[160];
static atomic_flag ail_api_guard = ATOMIC_FLAG_INIT;

typedef struct ail_api_allocation {
    void *payload;
    struct ail_api_allocation *next;
} ail_api_allocation;
static ail_api_allocation *ail_api_allocations;
typedef struct ail_api_stream {
    FILE *stream;
    struct ail_api_stream *next;
} ail_api_stream;
static ail_api_stream *ail_api_streams;

/* Call setjmp(ail_api_jump) immediately after a successful begin. */
static int ail_api_begin(void) {
    if (atomic_flag_test_and_set_explicit(&ail_api_guard, memory_order_acquire))
        return 0;
    ail_api_status = 0;
    ail_api_message[0] = '\0';
    ail_api_allocations = NULL;
    ail_api_streams = NULL;
    return 1;
}

static _Noreturn void ail_api_trap(int code, const char *message) {
    size_t i = 0;
    ail_api_status = code ? code : 8;
    if (message) {
        while (i < sizeof ail_api_message - 1 && message[i]) {
            ail_api_message[i] = message[i];
            ++i;
        }
    }
    ail_api_message[i] = '\0';
    longjmp(ail_api_jump, 1);
}

static void *ail_api_track(void *payload) {
    if (!payload) ail_api_trap(8, "allocation failed");
    ail_api_allocation *node = malloc(sizeof *node);
    if (!node) {
        free(payload);
        ail_api_trap(8, "allocation tracking failed");
    }
    node->payload = payload;
    node->next = ail_api_allocations;
    ail_api_allocations = node;
    return payload;
}

/* Native payload pointers retain malloc alignment and native-free ownership. */
static void *ail_api_malloc(size_t size) {
    return ail_api_track(malloc(size ? size : 1));
}

static void *ail_api_calloc(size_t count, size_t size) {
    if (size && count > SIZE_MAX / size) {
        errno = ENOMEM;
        ail_api_trap(8, "allocation size overflow");
    }
    return ail_api_track(count && size ? calloc(count, size) : calloc(1, 1));
}

static ail_api_allocation **ail_api_find(void *payload) {
    ail_api_allocation **link = &ail_api_allocations;
    while (*link && (*link)->payload != payload) link = &(*link)->next;
    if (!*link) ail_api_trap(8, "allocation is not owned by this call");
    return link;
}

static void ail_api_free(void *payload) {
    if (!payload) return;
    ail_api_allocation **link = ail_api_find(payload);
    ail_api_allocation *node = *link;
    *link = node->next;
    free(payload);
    free(node);
}

static void *ail_api_realloc(void *payload, size_t size) {
    if (!payload) return ail_api_malloc(size);
    ail_api_allocation **link = ail_api_find(payload);
    if (!size) {
        ail_api_free(payload);
        return NULL;
    }
    void *replacement = realloc(payload, size);
    if (!replacement) ail_api_trap(8, "reallocation failed");
    (*link)->payload = replacement;
    return replacement;
}

/* Detach only after all fallible work succeeds; the caller owns the payload. */
static void ail_api_detach(void *payload) {
    if (!payload) return;
    ail_api_allocation **link = ail_api_find(payload);
    ail_api_allocation *node = *link;
    *link = node->next;
    free(node);
}

static FILE *ail_api_track_stream(FILE *stream) {
    if (!stream) return NULL;
    ail_api_stream *node = malloc(sizeof *node);
    if (!node) {
        fclose(stream);
        ail_api_trap(8, "stream tracking failed");
    }
    node->stream = stream;
    node->next = ail_api_streams;
    ail_api_streams = node;
    return stream;
}

static FILE *ail_api_fopen(const char *path, const char *mode) {
    return ail_api_track_stream(fopen(path, mode));
}

#ifdef _WIN32
static FILE *ail_api_wfopen(const wchar_t *path, const wchar_t *mode) {
    return ail_api_track_stream(_wfopen(path, mode));
}
#endif

static int ail_api_fclose(FILE *stream) {
    ail_api_stream **link = &ail_api_streams;
    while (*link && (*link)->stream != stream) link = &(*link)->next;
    if (!*link) ail_api_trap(8, "stream is not owned by this call");
    ail_api_stream *node = *link;
    *link = node->next;
    free(node);
    return fclose(stream);
}

/* Also called after longjmp; status and message remain available to wrappers. */
static void ail_api_finish(void) {
    while (ail_api_streams) {
        ail_api_stream *node = ail_api_streams;
        ail_api_streams = node->next;
        fclose(node->stream);
        free(node);
    }
    while (ail_api_allocations) {
        ail_api_allocation *node = ail_api_allocations;
        ail_api_allocations = node->next;
        free(node->payload);
        free(node);
    }
    atomic_flag_clear_explicit(&ail_api_guard, memory_order_release);
}
'''
