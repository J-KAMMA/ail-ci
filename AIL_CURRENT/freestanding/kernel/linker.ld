/* Linker script of the toy kernel: loaded at 1 MiB, multiboot headers first.
   gcc -ffreestanding -nostdlib -static -no-pie -T linker.ld -o kernel.elf boot.o ... */
ENTRY(_start)

SECTIONS
{
    . = 1M;

    /* the multiboot1 header must lie in the first 8 KiB of the file, multiboot2 in the first 32 KiB */
    .multiboot1 : { KEEP(*(.multiboot1)) }
    .multiboot2 : { KEEP(*(.multiboot2)) }

    .text : ALIGN(16) { *(.boot) *(.text .text.*) }
    .rodata : ALIGN(16) { *(.rodata .rodata.*) }

    . = ALIGN(4096);
    .data : { *(.data .data.*) }
    .bss : ALIGN(4096) { *(COMMON) *(.bss .bss.*) }

    . = ALIGN(4096);
    _kernel_end = .;

    /DISCARD/ : { *(.comment) *(.eh_frame) *(.note .note.*) }
}
