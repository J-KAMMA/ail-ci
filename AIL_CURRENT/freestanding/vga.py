"""A VGA text-mode writer over 80x25 character cells (low byte the character, high byte the colour).

In a kernel the cells are the memory-mapped window at 0xB8000:  screen = Ptr[u16](0xB8000).
Here they are a static array, so a hosted harness (and CPython) can read what was written; every
store and load still goes through volatile_store / volatile_load as it would to the device.
"""
from ail_freestanding import u8, u16, u32, Array, Ptr, extern, wrapping, as_ptr, volatile_load, volatile_store

WIDTH = 80
HEIGHT = 25
BLANK = 0x20

vga_buffer: Array[u16, 2000] = Array[u16, 2000]()
vga_row: u32 = 0
vga_col: u32 = 0
vga_color: u8 = 0x07


@extern
def vga_cursor_moved(position: u16) -> None:
    """The kernel moves the hardware cursor (ports 0x3D4/0x3D5); the harness records it."""


def vga_cell(c: u8, color: u8) -> u16:
    return u16(c) | (u16(color) << 8)


def _screen() -> Ptr[u16]:
    return as_ptr(vga_buffer)


@wrapping
def vga_clear() -> None:
    global vga_row, vga_col
    screen = _screen()
    for i in range(u32(WIDTH * HEIGHT)):
        volatile_store(screen.offset(i), vga_cell(BLANK, vga_color))
    vga_row = 0
    vga_col = 0
    vga_cursor_moved(u16(0))


@wrapping
def _scroll() -> None:
    screen = _screen()
    for i in range(u32(WIDTH * (HEIGHT - 1))):
        volatile_store(screen.offset(i), volatile_load(screen.offset(i + WIDTH)))
    for i in range(u32(WIDTH * (HEIGHT - 1)), u32(WIDTH * HEIGHT)):
        volatile_store(screen.offset(i), vga_cell(BLANK, vga_color))


@wrapping
def vga_putc(c: u8) -> None:
    global vga_row, vga_col
    match c:
        case 10:
            vga_col = 0
            vga_row += 1
        case 13:
            vga_col = 0
        case 8:
            if vga_col > 0:
                vga_col -= 1
                volatile_store(_screen().offset(vga_row * WIDTH + vga_col), vga_cell(BLANK, vga_color))
        case _:
            volatile_store(_screen().offset(vga_row * WIDTH + vga_col), vga_cell(c, vga_color))
            vga_col += 1
            if vga_col == WIDTH:
                vga_col = 0
                vga_row += 1
    if vga_row == HEIGHT:
        _scroll()
        vga_row = HEIGHT - 1
    vga_cursor_moved(u16(vga_row * WIDTH + vga_col))


def vga_write(text: Ptr[u8], n: u32) -> None:
    for i in range(n):
        vga_putc(text[i])


@wrapping
def vga_checksum() -> u32:
    """FNV-1a over every cell."""
    h: u32 = 2166136261
    for i in range(u32(WIDTH * HEIGHT)):
        h = (h ^ u32(vga_buffer[i])) * 16777619
    return h


@wrapping
def vga_selftest(seed: u32) -> u32:
    """Clear, then write pseudo-random text with newlines and backspaces; the screen's checksum."""
    global vga_color
    vga_clear()
    state: u32 = seed
    for _ in range(u32(2500)):
        state = state * 1103515245 + 12345
        k = (state >> 16) % 40
        if k == 0:
            vga_putc(10)
        elif k == 1:
            vga_putc(8)
        elif k == 2:
            vga_color = u8(state >> 24)
        else:
            vga_putc(u8(33 + (state >> 8) % 94))
    return vga_checksum() ^ (vga_row * WIDTH + vga_col)
