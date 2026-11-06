# robo1 results: AIL on ARM and on a microcontroller

All numbers are from `results.json` (`python3 lab/robo/run.py`, 3 repetitions, Ubuntu 24.04.5
runner, gcc 13.3.0, arm-none-eabi-gcc 13.2.1 + newlib-nano 4.4.0, QEMU 8.2.2, MicroPython
1.22.1). Versions and method are in `README.md`.

## 1. Cross-build table

`-O2 -fno-tree-slp-vectorize -ffp-contract=off -fopenmp-simd -fno-asynchronous-unwind-tables -lm`,
the flags AIL uses natively (minus its three `-Werror=` diagnostic flags, which change no code).
Sizes are `size` text+data+bss of the linked executable in bytes. "match" compares the full stdout
with CPython 3.12.3; the exit status was 0 everywhere.

| program | target | builds | first error | text | data | bss | runs | match |
|---|---|---|---|---|---|---|---|---|
| pid.py | x86-64 native | yes | - | 12846 | 848 | 4968 | yes | yes |
| pid.py | aarch64-linux-gnu (qemu-aarch64) | yes | - | 17837 | 944 | 20256 | yes | yes |
| pid.py | arm-linux-gnueabihf (qemu-arm) | yes | - | 9787 | 468 | 25376 | yes | yes |
| pid.py | arm-none-eabi Cortex-M3 (qemu-system-arm) | yes | - | 44636 | 468 | 11036 | yes | yes |
| ringbuf.py | x86-64 native | yes | - | 11550 | 848 | 4968 | yes | yes |
| ringbuf.py | aarch64-linux-gnu | yes | - | 17003 | 944 | 20256 | yes | yes |
| ringbuf.py | arm-linux-gnueabihf | yes | - | 10239 | 472 | 25376 | yes | yes |
| ringbuf.py | arm-none-eabi Cortex-M3 | yes | - | 44644 | 468 | 11036 | yes | yes |
| kin2.py | x86-64 native | yes | - | 11535 | 984 | 5000 | yes | yes |
| kin2.py | aarch64-linux-gnu | yes | - | 16427 | 1080 | 20264 | yes | yes |
| kin2.py | arm-linux-gnueabihf | yes | - | 8441 | 532 | 25376 | yes | yes |
| kin2.py | arm-none-eabi Cortex-M3 | yes | - | 48828 | 468 | 11036 | yes | yes |

Two build facts behind the bare-metal "yes" cells:

- **Bare metal needs `-u _printf_float`.** Without it newlib-nano's `printf` has no float
  formatter: the same image links, runs, and prints `0.0` for every float (verified with a
  `1.5*2.25+0.5` probe: `3.875 7.5 4.0` became `0.0 0.0 0.0`). Integer output is unaffected, so
  this fails silently for a control program. It is a link flag, not a source change.
- The runtime is one C file, but AIL emits only the runtime a program reaches: `pid.py`'s
  `program.c` is 3,232 lines with 0 references to `pthread`, `mmap`, `socket`, `clock_gettime` or
  `nanosleep`. That is why a 44 KB Cortex-M3 image with none of those subsystems links at all;
  gcc dead-code elimination is not what makes it small (section 2).

Confirmed with `bash ~/tools/cmp.sh` on all three programs: the general path (`AIL_UNIFIED_FORCE=1`)
and the default build both print exactly what CPython prints (3/3 programs, 2/2 builds).

## 2. Bare-metal blocker census

Each row is an actual build attempt of a small AIL program that uses that subsystem, with the same
newlib-nano + rdimon harness. The "first error" is the compiler's first line. Runtime functions are
in `AIL_CURRENT/python/pkg-v12/cruntime.py` (the runtime is emitted into `program.c`).

| area | first bare-metal error | runtime function | what is missing | one-line stub idea |
|---|---|---|---|---|
| threading (`threading.Thread`) | `program.c:5972:9: error: expected expression before '__int128'` | `ail_op_getslice` (boxed runtime); next `SSIZE_MAX` in `ail_bi_line_append`; 12 distinct `pthread_*` names | the boxed/general path uses `__int128`, which 32-bit arm-none-eabi does not have; newlib then has no pthread | make the boxed runtime 32-bit safe (pair of 64-bit ops instead of `__int128`), then a single-thread build flag |
| parallel loop (`ail.par_range`) | `program.c:473:5: error: unknown type name 'pthread_mutex_t'` | `ail_par_job`, `ail_par_pool_main`, `ail_par_wait` | newlib-nano's `pthread.h` has no `pthread_mutex_t` / `pthread_cond_t` / `pthread_t` and no `PTHREAD_*_INITIALIZER` | an `AIL_PAR_SERIAL` build that runs each block on the calling thread; the typed code needs no other change |
| TCP (`ail.tcp_listen`) | `program.c:18:10: fatal error: sys/socket.h: No such file or directory` | `ail_tcpsocket_connect`, `ail_tcpsocket_close` | newlib has no socket headers; `socket`/`getaddrinfo` are absent | refuse `tcp_*` at build time for a bare-metal profile, or port to lwIP |
| large file read (`read_bytes` of 2 MiB, iterated) | `program.c:3448:10: fatal error: sys/mman.h: No such file or directory` | `ail_win_map`, `ail_win_drop` (IR window runtime) | `mmap`, `munmap`, `madvise`, `sysconf(_SC_PAGESIZE)`, `S_ISREG` | the runtime already falls back to `read()` when `mmap` fails; the header and the type names must still exist, or set `AIL_IR_WINDOW_MIN` out of reach |
| clock / sleeping (`time.perf_counter`, `time.sleep`) | `program.c:479:23: error: 'CLOCK_MONOTONIC' undeclared (first use in this function)` | `ail_perf_counter_ns` and the `time.sleep` helper | newlib-nano defines neither `CLOCK_MONOTONIC` nor `clock_gettime`/`nanosleep` (checked with `nm` on `libc_nano.a`) | define `CLOCK_MONOTONIC` and provide `clock_gettime`/`nanosleep` over SysTick or the vendor HAL |
| file I/O (`read_bytes`/`write_bytes`) | builds and runs | `ail_*file*` via stdio | nothing: newlib + librdimon semihosting provides `fopen`/`read`/`write` | no stub needed; heap peak 65,576 B (stdio buffer) |
| environment (`ail.get_env`) | builds and runs: prints `PATH = missing` bare metal (the fallback; native prints the real `PATH`) | `ail_get_env` | `getenv` exists but returns NULL under semihosting (no environment) | inject a small key/value table |
| signals | not applicable | - | AIL's documented Python subset has no `signal` module, so the runtime needs no signal symbols | - |

Also confirmed absent from newlib-nano: `mmap`, `munmap`, `nanosleep`, `clock_gettime`,
`pthread_create`. Present: `getenv`, `sysconf`, `sbrk`, `setjmp`/`longjmp`, `malloc`, stdio.

## 3. Control-loop jitter, 1 kHz, 20 000 iterations

Deadline miss in microseconds; median of 3 runs (each run's histogram gives nearest-rank p50/p99/p99.9;
`max` is the exact maximum, rounded here to the nearest microsecond). "overruns" = iterations whose
wake-up was at least one whole period (1000 us) late.
This is a shared GitHub Actions VM: the C row is the noise floor, not a guarantee.

| variant | tool | p50 | p99 | p99.9 | max | overruns |
|---|---|---|---|---|---|---|
| noalloc | C (clock_nanosleep, absolute) | 59 | 66 | 98 | 271 | 0 |
| noalloc | AIL (perf_counter + time.sleep) | 60 | 68 | 108 | 247 | 0 |
| noalloc | MicroPython (time_ns + sleep_us) | 61 | 71 | 114 | 5596 | 5 |
| alloc | C (malloc/free per iteration) | 60 | 69 | 99 | 277 | 0 |
| alloc | AIL (list(state) per iteration) | 60 | 69 | 94 | 405 | 0 |
| alloc | MicroPython (list(state) per iteration) | 61 | 72 | 110 | 5745 | 5 |

Reading: at 1 kHz the language is invisible in the body of the distribution - all three sit at the
kernel's ~60 us timer slack (p50 59-61 us, p99 66-72 us). The difference is in the tail: C and AIL
had no overrun in any run (worst miss 271-406 us), while MicroPython overran 5-7 times in every run
and its worst miss was 5.4-6.1 ms, about 20x the C worst case. Allocation does not move the C or
AIL numbers.

## 4. RAM

Linux: peak RSS of the process. The qemu rows include the emulator (9-11 MB baseline), so they are
an upper bound, not the guest's own footprint. Bare metal: heap high-water from the
`--wrap=malloc` counter in `harness/memcount.c` (allocation calls through the public
`malloc/calloc/realloc/free`; it does see libc's own buffers, e.g. 65,576 B for the stdio file probe).

| program | native RSS | aarch64 RSS (qemu) | armhf RSS (qemu) | bare-metal heap peak | bare-metal .data+.bss |
|---|---|---|---|---|---|
| pid.py | 1,644 KB | 10,588 KB | 9,440 KB | 224 B | 468 + 11,036 B |
| ringbuf.py | 1,704 KB | 10,464 KB | 9,400 KB | 88 B | 468 + 11,036 B |
| kin2.py | 2,152 KB | 10,908 KB | 10,692 KB | 20 B | 468 + 11,036 B |

The 11,036 B of `.bss` on Cortex-M3 is the runtime's static state (arena headers, stdio, exception
stack), not program data: the three programs allocate 20-224 B of heap for their whole run.

## Verdict

1. AIL's generated C cross-compiles untouched to aarch64, armhf and Cortex-M3 and prints the same
   bytes as CPython on all three programs: the simple typed path is already usable on a robot's Pi
   or MCU today.
2. Smallest missing piece for control: an absolute-deadline timer (`clock_nanosleep`, or a
   `sleep_until` HAL call); AIL only exposes relative `time.sleep`.
3. Next: an embedded target profile that omits pthread/socket/mmap/clock headers and serializes
   `par_range`; the typed runtime is otherwise small (44-49 KB text, 11 KB bss).
4. Then: a 32-bit-safe boxed runtime (`__int128`, `SSIZE_MAX`) for programs that fall back to the
   general path, and `-u _printf_float` (or an internal float formatter) as an automatic link
   flag so float output cannot silently become `0.0`.
5. It already beats MicroPython where a control loop cares: no GC tail (0 overruns vs 5 per 20,000,
   worst miss 0.2-0.6 ms vs 5.4-6.1 ms) and 20-224 B of heap vs MicroPython's interpreter heap.
6. Not measured: real hardware, interrupt latency, an RTOS/CMSIS integration, and long-run thermal
   or clock drift; the jitter numbers come from a noisy shared x86 runner.
