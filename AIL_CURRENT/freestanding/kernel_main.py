"""The AIL side of the toy kernel's first step: kernel_main writes to the VGA text window and halts.

The multiboot2 entry stub (C/asm, docs/design/FREESTANDING.md section 6) sets up a stack and calls
kernel_main(magic, info). This module only compiles and links here; running it needs QEMU.
"""
from ail_freestanding import u8, u16, u32, usize, Ptr, extern, wrapping, asm, volatile_store

VGA_TEXT = 0xB8000
MULTIBOOT2_MAGIC = 0x36D76289
COM1 = 0x3F8


@extern
def outb(port: u16, value: u8) -> None:
    """Defined by the entry stub: out %al, %dx."""


@wrapping
def serial_write(text: Ptr[u8], n: u32) -> None:
    for i in range(n):
        outb(u16(COM1), text[i])


@wrapping
def kernel_main(magic: u32, info: usize) -> None:
    screen = Ptr[u16](VGA_TEXT)
    color: u16 = 0x2F00 if magic == MULTIBOOT2_MAGIC else 0x4F00
    volatile_store(screen.offset(0), color | 0x41)      # 'A'
    volatile_store(screen.offset(1), color | 0x49)      # 'I'
    volatile_store(screen.offset(2), color | 0x4C)      # 'L'
    asm("cli")
    while True:
        asm("hlt")
