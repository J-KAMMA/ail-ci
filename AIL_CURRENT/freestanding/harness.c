/* Hosted test harness for the freestanding examples (test_ail_freestanding.py).

   Links ring.o, pagealloc.o, crc32.o and vga.o -- each built by
   `ail_chatgpt.py compile --freestanding X.py -o X.o` -- and calls them like a kernel would.
   Direct checks print "FAIL ..." and exit 1; the selftest lines ("ring 3 123...") are compared by
   the test with the same functions run on CPython through ail_freestanding.load. */
#include <inttypes.h>
#include <stdio.h>
#include <string.h>

#include "ring.h"
#include "pagealloc.h"
#include "crc32.h"
#include "vga.h"

static int failures;
static unsigned cursor_calls;
static uint16_t cursor_last;

void vga_cursor_moved(uint16_t position) {
    cursor_calls++;
    cursor_last = position;
}

#define CHECK(cond) do { if (!(cond)) { printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond); failures++; } } while (0)

static void check_ring(void) {
    CHECK(Ring_is_empty(&keyboard));
    CHECK(Ring_pop(&keyboard) == 0x100);
    for (unsigned i = 0; i < 256; i++)
        CHECK(Ring_push(&keyboard, (uint8_t)i));
    CHECK(!Ring_push(&keyboard, 1));                  /* full */
    CHECK(Ring_count(&keyboard) == 256);
    for (unsigned i = 0; i < 256; i++)
        CHECK(Ring_pop(&keyboard) == i);
    CHECK(Ring_is_empty(&keyboard));
    Ring r;
    memset(&r, 0, sizeof r);
    r.head = r.tail = 0xFFFFFFFEu;                     /* the counters wrap */
    CHECK(Ring_push(&r, 7) && Ring_push(&r, 8) && Ring_push(&r, 9));
    CHECK(r.head == 1 && Ring_count(&r) == 3);
    CHECK(Ring_pop(&r) == 7 && Ring_pop(&r) == 8 && Ring_pop(&r) == 9 && Ring_pop(&r) == 0x100);
}

static void check_pages(void) {
    pa_init(&frames, 0x100000, 3);
    uintptr_t a = pa_alloc(&frames), b = pa_alloc(&frames), c = pa_alloc(&frames);
    CHECK(a == 0x100000 && b == 0x101000 && c == 0x102000);
    CHECK(pa_alloc(&frames) == 0);                    /* only three pages */
    CHECK(frames.used == 3);
    CHECK(pa_free(&frames, b));
    CHECK(!pa_free(&frames, b));                      /* double free */
    CHECK(!pa_free(&frames, b + 1));                  /* unaligned */
    CHECK(!pa_free(&frames, 0x0FF000));               /* below the range */
    CHECK(!pa_free(&frames, 0x103000));               /* past npages */
    CHECK(!pa_is_used(&frames, 1) && pa_is_used(&frames, 0));
    CHECK(pa_alloc(&frames) == b);
    pa_init(&frames, 0x200000, 100000);               /* clamped to MAX_PAGES */
    CHECK(frames.npages == 4096);
}

static void check_crc(void) {
    static const char *texts[] = {"", "a", "123456789", "The quick brown fox jumps over the lazy dog"};
    static const uint32_t want[] = {0x00000000u, 0xE8B7BE43u, 0xCBF43926u, 0x414FA339u};
    for (int i = 0; i < 4; i++) {
        uint32_t got = crc32_update(0, (uint8_t *)texts[i], strlen(texts[i]));
        if (got != want[i]) { printf("FAIL crc32(%s) = %08" PRIx32 "\n", texts[i], got); failures++; }
    }
    /* in two pieces gives the same */
    const char *s = "123456789";
    CHECK(crc32_update(crc32_update(0, (uint8_t *)s, 4), (uint8_t *)s + 4, 5) == 0xCBF43926u);
    CHECK(crc_table[1] == 0x77073096u && crc_table[255] == 0x2D02EF8Du);
}

static void check_vga(void) {
    vga_clear();
    CHECK(vga_buffer[0] == 0x0720 && vga_buffer[1999] == 0x0720);
    CHECK(cursor_calls == 1 && cursor_last == 0);
    vga_write((uint8_t *)"Hi\nAIL", 6);
    CHECK(vga_buffer[0] == 0x0748 && vga_buffer[1] == 0x0769);
    CHECK(vga_buffer[80] == 0x0741 && vga_buffer[82] == 0x074C);
    CHECK(vga_row == 1 && vga_col == 3 && cursor_last == 83);
    vga_putc(8);
    CHECK(vga_col == 2 && vga_buffer[82] == 0x0720);
    for (int i = 0; i < 30; i++)
        vga_putc('\n');
    CHECK(vga_row == 24 && vga_col == 0);                /* scrolled, not past the last row */
}

int main(void) {
    check_ring();
    check_pages();
    check_crc();
    check_vga();
    for (uint32_t seed = 0; seed < 12; seed++) {
        printf("ring %" PRIu32 " %" PRIu32 "\n", seed, ring_selftest(seed));
        printf("pages %" PRIu32 " %" PRIu64 "\n", seed, pa_selftest(seed));
        printf("vga %" PRIu32 " %" PRIu32 "\n", seed, vga_selftest(seed));
    }
    printf("%s\n", failures ? "FAILED" : "OK");
    return failures != 0;
}
