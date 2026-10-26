/* Entry stub of the toy kernel (docs/design/FREESTANDING.md section 7).

   Two multiboot headers, one image:
     - multiboot2 (GRUB2: `multiboot2 /boot/kernel.elf`), in the first 32 KiB of the file;
     - multiboot1 (QEMU `-kernel` only understands this one), in the first 8 KiB.
   Either loader enters _start in 32-bit protected mode with paging off, eax = the loader's magic and
   ebx = the physical address of its information structure. The stub builds an identity map of the
   first GiB with 2 MiB pages, switches to long mode and calls the AIL function
   kernel_main(magic: u32, info: usize) with the System V arguments (edi, rsi).

   Also here: kernel_end_addr(), because linker symbols are not reachable from AIL. */

        .set MB1_MAGIC, 0x1BADB002
        .set MB1_FLAGS, 0x00000003              /* bit 0: modules page aligned, bit 1: memory info */
        .set MB2_MAGIC, 0xE85250D6
        .set MB2_ARCH, 0                        /* i386 protected mode */

        .section .multiboot1, "a"
        .align 4
        .long MB1_MAGIC
        .long MB1_FLAGS
        .long -(MB1_MAGIC + MB1_FLAGS)          /* flag bit 16 clear: the loader uses the ELF headers */

        .section .multiboot2, "a"
        .align 8
mb2_start:
        .long MB2_MAGIC
        .long MB2_ARCH
        .long mb2_end - mb2_start
        .long -(MB2_MAGIC + MB2_ARCH + (mb2_end - mb2_start))
        .short 0                                /* end tag: type 0, flags 0, size 8 */
        .short 0
        .long 8
mb2_end:

        .section .bss
        .align 4096
pml4:   .skip 4096
pdpt:   .skip 4096
pd:     .skip 4096
        .align 16
stack_bottom:
        .skip 16384
stack_top:
boot_magic: .skip 4
boot_info:  .skip 4

        .section .rodata
        .align 8
gdt64:
        .quad 0
        .quad 0x00AF9A000000FFFF               /* 0x08: 64-bit code, ring 0 */
        .quad 0x00CF92000000FFFF               /* 0x10: data */
gdt64_end:
gdt64_ptr:
        .word gdt64_end - gdt64 - 1
        .long gdt64

        .code32
        .section .boot, "ax"
        .global _start
        .type _start, @function
_start:
        cli
        cld
        movl %eax, boot_magic
        movl %ebx, boot_info
        movl $stack_top, %esp

        /* long mode needs CPUID extended leaf 0x80000001, EDX bit 29 */
        movl $0x80000000, %eax
        cpuid
        cmpl $0x80000001, %eax
        jb .Lno_long_mode
        movl $0x80000001, %eax
        cpuid
        testl $(1 << 29), %edx
        jz .Lno_long_mode

        /* clear the three page tables, then pml4[0] -> pdpt[0] -> pd[0..511] = 2 MiB pages */
        movl $pml4, %edi
        xorl %eax, %eax
        movl $(3 * 4096 / 4), %ecx
        rep stosl
        movl $pdpt, %eax
        orl $0x3, %eax                          /* present, writable */
        movl %eax, pml4
        movl $pd, %eax
        orl $0x3, %eax
        movl %eax, pdpt
        xorl %ecx, %ecx
1:      movl %ecx, %eax
        shll $21, %eax
        orl $0x83, %eax                         /* present, writable, 2 MiB page */
        movl %eax, pd(, %ecx, 8)
        incl %ecx
        cmpl $512, %ecx
        jne 1b

        movl $pml4, %eax
        movl %eax, %cr3
        movl %cr4, %eax
        orl $0x20, %eax                         /* PAE */
        movl %eax, %cr4
        movl $0xC0000080, %ecx                  /* EFER */
        rdmsr
        orl $0x100, %eax                        /* LME */
        wrmsr
        movl %cr0, %eax
        orl $0x80000001, %eax                   /* PG | PE */
        movl %eax, %cr0
        lgdt gdt64_ptr
        ljmp $0x08, $long_entry

.Lno_long_mode:
        movl $0x4F4C4F4E, 0xB8000               /* "NO" in white on red: no 64-bit CPU */
1:      hlt
        jmp 1b
        .size _start, . - _start

        .code64
        .type long_entry, @function
long_entry:
        movw $0x10, %ax
        movw %ax, %ds
        movw %ax, %es
        movw %ax, %fs
        movw %ax, %gs
        movw %ax, %ss
        movq $stack_top, %rsp
        xorl %ebp, %ebp
        movl boot_magic, %edi
        movl boot_info, %esi
        call kernel_main
1:      cli
        hlt
        jmp 1b
        .size long_entry, . - long_entry

        .section .text
        .global kernel_end_addr
        .type kernel_end_addr, @function
kernel_end_addr:
        leaq _kernel_end(%rip), %rax
        ret
        .size kernel_end_addr, . - kernel_end_addr

        .section .note.GNU-stack, "", @progbits
