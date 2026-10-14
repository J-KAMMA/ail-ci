/* C ABI leaf function: sum seven words modulo 2^64, return the signed bit pattern. */
#if !defined(__x86_64__) || (!defined(_WIN32) && !defined(__linux__))
#error This example requires x86_64 Windows or Linux
#endif
.text
.globl native_accumulate7
#ifndef _WIN32
.type native_accumulate7, @function
#endif
native_accumulate7:
#ifdef _WIN32
    movq %rcx, %rax
    addq %rdx, %rax
    addq %r8, %rax
    addq %r9, %rax
    addq 40(%rsp), %rax
    addq 48(%rsp), %rax
    addq 56(%rsp), %rax
#else
    movq %rdi, %rax
    addq %rsi, %rax
    addq %rdx, %rax
    addq %rcx, %rax
    addq %r8, %rax
    addq %r9, %rax
    addq 8(%rsp), %rax
#endif
    ret
#ifndef _WIN32
.size native_accumulate7, .-native_accumulate7
.section .note.GNU-stack,"",@progbits
#endif
