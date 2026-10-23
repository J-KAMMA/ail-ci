"""Toy kernel console: VGA text mode (80x25 at 0xB8000) and the COM1 serial port.

Port I/O is two function pointers (con_out, con_in) that start as the real `out`/`in` instructions,
written as inline assembly with operands. The hosted test harness replaces them with a recorder and
points con_screen at a plain array, so everything below except the two asm functions runs on the
build machine. Run on hardware, `qemu -serial stdio` shows the serial text.
"""
from ail_freestanding import u8, u16, u32, u64, Array, Ptr, Fn, arithmetic, asm, volatile_load, volatile_store

arithmetic("wrapping")

COLS = 80
ROWS = 25
BLANK = 0x20
COM1 = 0x3F8
VGA_TEXT = 0xB8000


def hw_outb(port: u16, value: u8) -> None:
    asm("outb %0, %1", inputs=[("a", value), ("Nd", port)])


def hw_inb(port: u16) -> u8:
    value: u8 = 0
    asm("inb %1, %0", outputs=[("=a", value)], inputs=[("Nd", port)])
    return value


con_out: Fn[[u16, u8], None] = hw_outb
con_in: Fn[[u16], u8] = hw_inb
con_screen: Ptr[u16] = Ptr[u16](VGA_TEXT)
con_row: u32 = 0
con_col: u32 = 0
con_color: u8 = 0x07


def outb(port: u16, value: u8) -> None:
    """The port-write function the other kernel modules declare with @extern."""
    con_out(port, value)


def serial_init() -> None:
    """COM1 at 38400 baud, 8N1, FIFO on, no interrupts."""
    con_out(u16(COM1 + 1), 0)
    con_out(u16(COM1 + 3), 0x80)
    con_out(u16(COM1 + 0), 3)
    con_out(u16(COM1 + 1), 0)
    con_out(u16(COM1 + 3), 3)
    con_out(u16(COM1 + 2), 0xC7)
    con_out(u16(COM1 + 4), 0x0B)


def serial_putc(c: u8) -> None:
    for _ in range(u32(65536)):
        if con_in(u16(COM1 + 5)) & 0x20 != 0:
            break
    con_out(u16(COM1), c)


def vga_cell(c: u8, color: u8) -> u16:
    return u16(c) | (u16(color) << 8)


def vga_cursor() -> None:
    pos = u16(con_row * COLS + con_col)
    con_out(u16(0x3D4), 14)
    con_out(u16(0x3D5), u8(pos >> 8))
    con_out(u16(0x3D4), 15)
    con_out(u16(0x3D5), u8(pos & 0xFF))


def vga_clear() -> None:
    global con_row, con_col
    for i in range(u32(COLS * ROWS)):
        volatile_store(con_screen.offset(i), vga_cell(BLANK, con_color))
    con_row = 0
    con_col = 0
    vga_cursor()


def vga_scroll() -> None:
    for i in range(u32(COLS * (ROWS - 1))):
        volatile_store(con_screen.offset(i), volatile_load(con_screen.offset(i + COLS)))
    for i in range(u32(COLS * (ROWS - 1)), u32(COLS * ROWS)):
        volatile_store(con_screen.offset(i), vga_cell(BLANK, con_color))


def vga_putc(c: u8) -> None:
    global con_row, con_col
    match c:
        case 10:
            con_col = 0
            con_row += 1
        case 13:
            con_col = 0
        case 8:
            if con_col > 0:
                con_col -= 1
                volatile_store(con_screen.offset(con_row * COLS + con_col), vga_cell(BLANK, con_color))
        case _:
            volatile_store(con_screen.offset(con_row * COLS + con_col), vga_cell(c, con_color))
            con_col += 1
            if con_col == COLS:
                con_col = 0
                con_row += 1
    if con_row == ROWS:
        vga_scroll()
        con_row = ROWS - 1
    vga_cursor()


def console_init() -> None:
    serial_init()
    vga_clear()


def console_putc(c: u8) -> None:
    if c == 10:
        serial_putc(13)
    serial_putc(c)
    vga_putc(c)


def console_write(text: Ptr[u8], n: u32) -> None:
    for i in range(n):
        console_putc(text[i])


def console_put_hex(v: u64) -> None:
    """0x followed by the digits without leading zeros (at least one)."""
    console_putc(48)
    console_putc(120)
    started: bool = False
    for i in range(u32(16)):
        shift: u32 = (15 - i) * 4
        d = u8((v >> shift) & 15)
        if started or d != 0 or i == 15:
            started = True
            console_putc(d + 48 if d < 10 else d + 87)


def console_put_dec(v: u64) -> None:
    digits = Array[u8, 20]()
    n: u32 = 0
    x: u64 = v
    while True:
        digits[n] = u8(x % 10) + 48
        n += 1
        x = x // 10
        if x == 0:
            break
    while n > 0:
        n -= 1
        console_putc(digits[n])
