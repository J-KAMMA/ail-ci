/* Force-included by tools/wasm_build.py (zig cc -target wasm32-wasi -include wasm_shim.h). Everything here sits
   behind __wasi__, so the file is inert for any other target. It papers over the libc pieces wasi-libc lacks
   without touching the runtime emitters: each gap either gets a working stand-in or stops loudly.

   setjmp/longjmp: wasm32-wasi has no setjmp unless the module uses the exception-handling proposal, which wasmtime
   27 does not run. setjmp here always returns 0 (a try block runs its body), and longjmp -- reached only when an
   exception is raised inside an open try block -- prints a message and exits 70, never a silent wrong result. */
#ifndef AIL_WASM_SHIM_H
#define AIL_WASM_SHIM_H
#ifdef __wasi__
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
