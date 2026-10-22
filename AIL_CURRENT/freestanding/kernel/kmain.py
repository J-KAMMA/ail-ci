"""Toy kernel main: boot information, the page allocator, the IDT, a breakpoint and three timer ticks.

boot.S calls kernel_main(magic, info) in long mode with the first GiB identity-mapped. The pure parts
(mb_upper_kib, usable_pages, align_up) are tested on the build machine over captured multiboot
structures; the rest needs QEMU (see docs/design/FREESTANDING.md, section 7).
"""
from ail_freestanding import u8, u16, u32, u64, usize, Array, Ptr, extern, arithmetic, as_ptr, asm

arithmetic("checked")

MB2_MAGIC = 0x36D76289          # multiboot2 loaders (GRUB2)
MB1_MAGIC = 0x2BADB002          # multiboot1 loaders (QEMU -kernel)
MB2_TAG_END = 0
MB2_TAG_MEMINFO = 4             # basic memory information: mem_lower, mem_upper in KiB
PAGE_SIZE = 4096
ONE_MIB = 0x100000
MAP_LIMIT = 0x40000000          # boot.S identity-maps the first GiB
DEBUG_EXIT_PORT = 0xF4          # QEMU -device isa-debug-exit,iobase=0xf4,iosize=0x04


@extern
def kernel_end_addr() -> usize:
    """Defined in boot.S: the first address past the kernel image."""


@extern
def outb(port: u16, value: u8) -> None:
    """Defined by console.py."""


@extern
def console_init() -> None:
    """Defined by console.py."""


@extern
def console_write(text: Ptr[u8], n: u32) -> None:
    """Defined by console.py."""


@extern
def console_put_hex(v: u64) -> None:
    """Defined by console.py."""


@extern
def console_put_dec(v: u64) -> None:
    """Defined by console.py."""


@extern
def idt_install() -> None:
    """Defined by idt.py."""


@extern
def idt_ticks() -> u64:
    """Defined by idt.py."""


@extern
def pa_global_init(base: usize, npages: u32) -> None:
    """Defined by pagealloc.py."""


@extern
def pa_global_alloc() -> usize:
    """Defined by pagealloc.py."""


@extern
def pa_global_free(address: usize) -> bool:
    """Defined by pagealloc.py."""


_msg_banner: Array[u8, 19] = Array[u8, 19](b"AIL toy kernel up.\n")
_msg_mb1: Array[u8, 12] = Array[u8, 12](b"multiboot1, ")
_msg_mb2: Array[u8, 12] = Array[u8, 12](b"multiboot2, ")
_msg_unknown: Array[u8, 19] = Array[u8, 19](b"unknown boot magic\n")
_msg_kib: Array[u8, 17] = Array[u8, 17](b" KiB above 1 MiB\n")
_msg_pages: Array[u8, 11] = Array[u8, 11](b"pages from ")
_msg_got: Array[u8, 10] = Array[u8, 10](b"allocated ")
_msg_reused: Array[u8, 14] = Array[u8, 14](b"freed, reused\n")
_msg_tick: Array[u8, 9] = Array[u8, 9](b"ticks ok\n")
_msg_done: Array[u8, 6] = Array[u8, 6](b"done.\n")
_msg_space: Array[u8, 1] = Array[u8, 1](b" ")
_msg_nl: Array[u8, 1] = Array[u8, 1](b"\n")


def align_up(value: usize, alignment: usize) -> usize:
    return (value + alignment - 1) & ~(alignment - 1)


def mb_upper_kib(magic: u32, info: usize) -> u32:
    """KiB of memory above 1 MiB according to the boot loader, or 0 when it did not say."""
    if magic == MB1_MAGIC:
        # struct { u32 flags; u32 mem_lower; u32 mem_upper; ... }, flags bit 0: the two fields are valid
        fields = Ptr[u32](info)
        if fields[0] & 1 != 0:
            return fields[2]
        return 0
    if magic == MB2_MAGIC:
        # u32 total_size, u32 reserved, then 8-byte-aligned tags { u32 type, u32 size, ... }
        total = Ptr[u32](info)[0]
        offset: u32 = 8
        while offset + 8 <= total:
            tag = Ptr[u32](info + usize(offset))
            if tag[0] == MB2_TAG_END or tag[1] < 8:
                return 0
            if tag[0] == MB2_TAG_MEMINFO and tag[1] >= 16:
                return tag[3]
            offset = offset + ((tag[1] + 7) & 0xFFFFFFF8)
    return 0


def usable_pages(upper_kib: u32, start: usize) -> u32:
    """Whole pages from `start` (page aligned, at or above 1 MiB) to the end of RAM or the mapped GiB."""
    end = usize(ONE_MIB) + usize(upper_kib) * 1024
    if end > MAP_LIMIT:
        end = MAP_LIMIT
    if end <= start:
        return 0
    return u32((end - start) // PAGE_SIZE)


def say(text: Ptr[u8], n: u32) -> None:
    console_write(text, n)


def debug_exit(code: u8) -> None:
    outb(DEBUG_EXIT_PORT, code)         # QEMU exits with (code << 1) | 1; real hardware ignores the port


def kernel_main(magic: u32, info: usize) -> None:
    console_init()
    say(as_ptr(_msg_banner), u32(len(_msg_banner)))
    if magic == MB2_MAGIC:
        say(as_ptr(_msg_mb2), u32(len(_msg_mb2)))
    elif magic == MB1_MAGIC:
        say(as_ptr(_msg_mb1), u32(len(_msg_mb1)))
    else:
        say(as_ptr(_msg_unknown), u32(len(_msg_unknown)))
    upper = mb_upper_kib(magic, info)
    console_put_dec(u64(upper))
    say(as_ptr(_msg_kib), u32(len(_msg_kib)))

    start = align_up(kernel_end_addr(), PAGE_SIZE)
    npages = usable_pages(upper, start)
    pa_global_init(start, npages)
    console_put_dec(u64(npages))
    say(as_ptr(_msg_pages), u32(len(_msg_pages)))
    console_put_hex(u64(start))
    say(as_ptr(_msg_nl), 1)

    first = pa_global_alloc()
    second = pa_global_alloc()
    say(as_ptr(_msg_got), u32(len(_msg_got)))
    console_put_hex(u64(first))
    say(as_ptr(_msg_space), 1)
    console_put_hex(u64(second))
    say(as_ptr(_msg_nl), 1)
    if pa_global_free(first) and pa_global_alloc() == first:
        say(as_ptr(_msg_reused), u32(len(_msg_reused)))

    idt_install()
    asm("int3")                         # isr_breakpoint logs it and returns here
    while idt_ticks() < 3:
        asm("sti; hlt")                 # sti delays one instruction, so the timer cannot slip in before hlt
    asm("cli")
    say(as_ptr(_msg_tick), u32(len(_msg_tick)))
    say(as_ptr(_msg_done), u32(len(_msg_done)))
    debug_exit(0x10)
    while True:
        asm("cli")
        asm("hlt")
