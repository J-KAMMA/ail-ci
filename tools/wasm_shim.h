/* Force-included by tools/wasm_build.py (zig cc -target wasm32-wasi -include wasm_shim.h). Everything here sits
   behind __wasi__, so the file is inert for any other target. It supplies the libc pieces wasi-libc leaves to the
   toolchain, without touching the runtime emitters.

   setjmp/longjmp (try/except): wasi-libc implements them on the WebAssembly exception-handling proposal
   (-mexception-handling -mllvm -wasm-enable-sjlj, run with `wasmtime -W exceptions=y`). LLVM throws with the tag
   __c_longjmp, which no library in zig's wasi-libc defines, so it is defined here (one translation unit per
   program). Built without exception handling, setjmp.h would refuse to compile; that build instead gets a
   setjmp that always returns 0 and a longjmp that stops loudly (exit 70), never a silent wrong result. */
#ifndef AIL_WASM_SHIM_H
#define AIL_WASM_SHIM_H
#ifdef __wasi__
#ifdef __wasm_exception_handling__
__asm__(".globl __c_longjmp\n.tagtype __c_longjmp i32\n__c_longjmp:\n");
#else
#define _SETJMP_H 1          /* musl's guard: the runtime's #include <setjmp.h> becomes a no-op */
#include <stdio.h>
#include <stdlib.h>
typedef long jmp_buf[1];
#define setjmp(buf) ((void)(buf), 0)
static __attribute__((noreturn, unused)) void ail_wasi_longjmp(void) {
    fflush(stdout);
    fputs("ail wasm32-wasi: an exception reached a try/except handler; setjmp/longjmp is not available "
          "on this target\n", stderr);
    exit(70);
}
#define longjmp(buf, val) ((void)(buf), (void)(val), ail_wasi_longjmp())
#endif
#endif
#endif
