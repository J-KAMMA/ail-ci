/* Hosted test harness for the pure parts of the toy kernel (test_ail_freestanding2.py).

   Links console.o, idt.o, pagealloc.o and kmain.o -- each built by `ail_chatgpt.py compile --freestanding`
   -- into an ordinary program. The two port-I/O function pointers become recorders, the VGA window a
   plain array, and the multiboot structures are captured by hand. Nothing here executes `out`, `in`,
   `lidt` or `hlt`; kernel_main itself needs QEMU. Prints "FAIL file:line: condition" and exits 1, or "OK". */
#include <inttypes.h>
#include <stdio.h>
#include <string.h>

#include "console.h"
#include "idt.h"
#include "pagealloc.h"
#include "kmain.h"

static int failures;
#define CHECK(cond) do { if (!(cond)) { printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond); failures++; } } while (0)

uintptr_t kernel_end_addr(void) { return 0x120000; }       /* boot.S defines it from the linker script */

static struct { uint16_t port; uint8_t value; } log_[8192];
static unsigned nlog;
static uint16_t screen[80 * 25];

static void rec_out(uint16_t port, uint8_t value) {
    if (nlog < 8192) { log_[nlog].port = port; log_[nlog].value = value; nlog++; }
}
static uint8_t rec_in(uint16_t port) { (void)port; return 0x20; }     /* serial line status: transmitter empty */

/* the bytes written to COM1's data register since `from`, as text */
static const char *serial_text(unsigned from) {
    static char text[8192];
    unsigned n = 0;
    for (unsigned i = from; i < nlog && n < sizeof text - 1; i++)
        if (log_[i].port == 0x3F8) text[n++] = (char)log_[i].value;
    text[n] = 0;
    return text;
}

static void check_console(void) {
    con_out = rec_out;
    con_in = rec_in;
    con_screen = screen;
    nlog = 0;
    console_init();
    static const struct { uint16_t port; uint8_t value; } init[] = {
        {0x3F9, 0}, {0x3FB, 0x80}, {0x3F8, 3}, {0x3F9, 0}, {0x3FB, 3}, {0x3FA, 0xC7}, {0x3FC, 0x0B},
        {0x3D4, 14}, {0x3D5, 0}, {0x3D4, 15}, {0x3D5, 0}};
    CHECK(nlog == sizeof init / sizeof init[0]);
    for (unsigned i = 0; i < nlog && i < sizeof init / sizeof init[0]; i++)
        CHECK(log_[i].port == init[i].port && log_[i].value == init[i].value);
    for (unsigned i = 0; i < 2000; i++)
        CHECK(screen[i] == 0x0720);

    nlog = 0;
    console_write((uint8_t *)"Hi\n", 3);
    CHECK(strcmp(serial_text(0), "Hi\r\n") == 0);
    CHECK(screen[0] == 0x0748 && screen[1] == 0x0769 && screen[2] == 0x0720);
    CHECK(con_row == 1 && con_col == 0);
    CHECK(log_[nlog - 1].port == 0x3D5 && log_[nlog - 1].value == 80);        /* cursor at row 1, column 0 */

    nlog = 0;
    console_put_hex(0xDEADBEEFull);
    console_putc(' ');
    console_put_hex(0);
    console_putc(' ');
    console_put_hex(0xFFFFFFFFFFFFFFFFull);
    CHECK(strcmp(serial_text(0), "0xdeadbeef 0x0 0xffffffffffffffff") == 0);
    nlog = 0;
    console_put_dec(0);
    console_putc(' ');
    console_put_dec(1234567890123ull);
    console_putc(' ');
    console_put_dec(18446744073709551615ull);
    CHECK(strcmp(serial_text(0), "0 1234567890123 18446744073709551615") == 0);

    console_init();
    for (int line = 0; line < 30; line++) {
        char text[8];
        snprintf(text, sizeof text, "x%02d\n", line);
        console_write((uint8_t *)text, 4);
    }
    CHECK(con_row == 24 && con_col == 0);
    for (int row = 0; row < 24; row++) {
        char want[4];
        snprintf(want, sizeof want, "x%02d", row + 6);
        for (int k = 0; k < 3; k++)
            CHECK((screen[row * 80 + k] & 0xFF) == (uint8_t)want[k]);
        CHECK(screen[row * 80 + 3] == 0x0720);
    }
    for (int k = 0; k < 80; k++)
        CHECK(screen[24 * 80 + k] == 0x0720);
    console_putc(8);                                              /* backspace at column 0 does nothing */
    CHECK(con_col == 0);
    console_putc('A');
    console_putc(8);
    CHECK(con_col == 0 && screen[24 * 80] == 0x0720);
    for (int k = 0; k < 85; k++)                                  /* wrapping at column 80 */
        console_putc('z');
    CHECK(con_row == 24 && con_col == 5 && screen[23 * 80] == 0x077A);
}

static void check_idt(void) {
    CHECK(idt_layout_ok());
    CHECK(sizeof(IdtEntry) == 16 && sizeof(IdtPointer) == 10 && sizeof(InterruptFrame) == 40);
    CHECK(_Alignof(IdtEntry) == 1 && _Alignof(IdtPointer) == 1);

    idt_set_gate(14, 0xFFFF800012345678ull, 1);
    static const uint8_t want[16] = {0x78, 0x56, 0x08, 0x00, 0x01, 0x8E, 0x34, 0x12, 0x00, 0x80, 0xFF, 0xFF, 0, 0, 0, 0};
    CHECK(memcmp(&idt_table[14], want, 16) == 0);
    CHECK(idt_gate_address(&idt_table[14]) == 0xFFFF800012345678ull);
    idt_set_gate(14, 0, 9);                                       /* ist keeps its low 3 bits */
    CHECK(idt_table[14].ist == 1 && idt_gate_address(&idt_table[14]) == 0);

    idt_build();
    static const struct { int vector; uintptr_t handler; } gates[] = {
        {0, (uintptr_t)isr_divide}, {3, (uintptr_t)isr_breakpoint}, {6, (uintptr_t)isr_invalid_opcode},
        {8, (uintptr_t)isr_double_fault}, {13, (uintptr_t)isr_general_protection}, {14, (uintptr_t)isr_page_fault},
        {32, (uintptr_t)isr_timer}, {1, (uintptr_t)isr_spurious}, {200, (uintptr_t)isr_spurious}, {255, (uintptr_t)isr_spurious}};
    for (unsigned i = 0; i < sizeof gates / sizeof gates[0]; i++)
        CHECK(idt_gate_address(&idt_table[gates[i].vector]) == gates[i].handler);
    for (int v = 0; v < 256; v++)
        CHECK(idt_table[v].selector == 8 && idt_table[v].type_attr == 0x8E && idt_table[v].reserved == 0);
    CHECK(idt_pointer.limit == 4095 && idt_pointer.base == (uintptr_t)idt_table);

    nlog = 0;
    pic_remap();
    static const struct { uint16_t port; uint8_t value; } pic[] = {
        {0x20, 0x11}, {0xA0, 0x11}, {0x21, 32}, {0xA1, 40}, {0x21, 4}, {0xA1, 2}, {0x21, 1}, {0xA1, 1}, {0x21, 0xFE}, {0xA1, 0xFF}};
    CHECK(nlog == sizeof pic / sizeof pic[0]);
    for (unsigned i = 0; i < nlog && i < sizeof pic / sizeof pic[0]; i++)
        CHECK(log_[i].port == pic[i].port && log_[i].value == pic[i].value);

    nlog = 0;
    pit_init(100);                                                /* 1193182 / 100 = 11931 = 0x2E9B */
    CHECK(nlog == 3 && log_[0].port == 0x43 && log_[0].value == 0x36);
    CHECK(log_[1].port == 0x40 && log_[1].value == 0x9B && log_[2].port == 0x40 && log_[2].value == 0x2E);

    nlog = 0;
    CHECK(idt_ticks() == 0);
    timer_tick();
    timer_tick();
    timer_tick();
    CHECK(idt_ticks() == 3 && nlog == 3);
    for (unsigned i = 0; i < nlog && i < 3; i++)
        CHECK(log_[i].port == 0x20 && log_[i].value == 0x20);

    nlog = 0;
    exception_log(14, 0x1234, 5);
    CHECK(idt_exceptions == 1 && idt_last_vector == 14 && idt_last_ip == 0x1234 && idt_last_error == 5);
    CHECK(strcmp(serial_text(0), "exception #14 at 0x1234 error: 0x5\r\n") == 0);
}

static void check_pages(void) {
    pa_global_init(0x200000, 10);
    uintptr_t first = pa_global_alloc(), second = pa_global_alloc();
    CHECK(first == 0x200000 && second == 0x201000 && pa_global_used() == 2);
    CHECK(pa_global_free(first) && !pa_global_free(first));
    CHECK(pa_global_alloc() == first);                            /* the freed page is handed out again */
    for (int i = 0; i < 8; i++)
        CHECK(pa_global_alloc() != 0);
    CHECK(pa_global_alloc() == 0 && pa_global_used() == 10);
}

static void check_kmain(void) {
    CHECK(align_up(0x1001, 4096) == 0x2000 && align_up(0x1000, 4096) == 0x1000 && align_up(0, 4096) == 0);
    CHECK(align_up(0x123456, 0x100000) == 0x200000);

    uint32_t mb1[4] = {1, 639, 130048, 0};
    CHECK(mb_upper_kib(0x2BADB002, (uintptr_t)mb1) == 130048);
    mb1[0] = 0;                                                   /* flags bit 0 clear: the fields are not valid */
    CHECK(mb_upper_kib(0x2BADB002, (uintptr_t)mb1) == 0);
    CHECK(mb_upper_kib(0x12345678, (uintptr_t)mb1) == 0);

    /* a multiboot2 structure: total size, reserved, a command-line tag (13 bytes, padded to 16), the basic
       memory tag, then the end tag */
    uint32_t mb2[16] __attribute__((aligned(8))) = {
        8 + 16 + 16 + 8, 0,
        1, 13, 0x4C494100, 0x00000000,                            /* type 1, size 13, "\0AIL"... */
        4, 16, 639, 129000,
        0, 8};
    CHECK(mb_upper_kib(0x36D76289, (uintptr_t)mb2) == 129000);
    mb2[6] = 5;                                                   /* the same tag with another type: no memory tag */
    CHECK(mb_upper_kib(0x36D76289, (uintptr_t)mb2) == 0);
    mb2[6] = 4;
    mb2[3] = 3;                                                   /* a tag size below 8 must stop the walk, not loop */
    CHECK(mb_upper_kib(0x36D76289, (uintptr_t)mb2) == 0);

    CHECK(usable_pages(130048, 0x120000) == (0x8000000 - 0x120000) / 4096);
    CHECK(usable_pages(2097152, 0x120000) == (0x40000000 - 0x120000) / 4096);     /* clamped to the mapped GiB */
    CHECK(usable_pages(0, 0x120000) == 0);
    CHECK(usable_pages(1024, 0x200000) == 0 && usable_pages(1024, 0x1FF000) == 1);
}

static uint32_t fnv(uint32_t h, uint32_t v) { return (h ^ v) * 16777619u; }

/* the same scenario runs on CPython through ail_freestanding.load; the test compares these four numbers */
static void scenario(void) {
    nlog = 0;
    console_init();
    console_write((uint8_t *)"Hello, kernel\n", 14);
    console_put_hex(0xCAFE);
    console_putc('\n');
    console_put_dec(4096);
    console_putc('\n');
    for (int i = 0; i < 30; i++) {
        char text[16];
        snprintf(text, sizeof text, "line %02d\n", i);
        console_write((uint8_t *)text, (uint32_t)strlen(text));
    }
    uint32_t hs = 2166136261u, ht = 2166136261u;
    for (int i = 0; i < 2000; i++)
        hs = fnv(hs, screen[i]);
    for (unsigned i = 0; i < nlog; i++)
        ht = fnv(ht, ((uint32_t)log_[i].port << 8) | log_[i].value);
    printf("console_scenario %u %u %u %u\n", hs, ht, (unsigned)con_row, (unsigned)con_col);
}

int main(void) {
    check_console();
    scenario();
    check_idt();
    check_pages();
    check_kmain();
    puts(failures ? "FAILED" : "OK");
    return failures ? 1 : 0;
}
