# robo1: robotics / embedded probe

Can AIL's generated C run on ARM and on a microcontroller, what blocks bare metal, and how steady
is a 1 kHz control loop compared with C and MicroPython?

This directory only measures. It does not change the compiler or the runtime. `RESULTS.md` has the
four tables and the verdict; `results.json` is the machine-readable form.

## Reproduce

```sh
sudo apt-get install -y gcc-aarch64-linux-gnu gcc-arm-linux-gnueabihf \
    libc6-dev-arm64-cross libc6-dev-armhf-cross gcc-arm-none-eabi libnewlib-arm-none-eabi \
    qemu-user qemu-system-arm micropython
python3 lab/robo/run.py              # about 8 minutes (3 x 20 000-iteration jitter runs per row)
python3 lab/robo/run.py --quick      # 2 000 iterations, about 2 minutes
python3 lab/robo/run.py --skip-jitter
```

`run.py` writes `results.json`; `RESULTS.md` was written from that file. Nothing outside
`lab/robo/` is touched, and no AIL file is edited.

## Exact versions

| tool | version |
|---|---|
| OS | Ubuntu 24.04.5 LTS (GitHub Actions runner, x86-64) |
| CPython (oracle) | 3.12.3 |
| gcc (native) | 13.3.0 (Ubuntu 13.3.0-6ubuntu2~24.04.1) |
| aarch64-linux-gnu-gcc | 13.3.0 (package `gcc-aarch64-linux-gnu` 4:13.2.0-7ubuntu1) |
| arm-linux-gnueabihf-gcc | 13.3.0 (package `gcc-arm-linux-gnueabihf` 4:13.2.0-7ubuntu1) |
| glibc sysroots | 2.39 (`libc6-dev-arm64-cross`, `libc6-dev-armhf-cross` 2.39-0ubuntu8cross1) |
| arm-none-eabi-gcc | 13.2.1 20231009 (package `gcc-arm-none-eabi` 15:13.2.rel1-2) |
| newlib / newlib-nano | 4.4.0.20231231 (package `libnewlib-arm-none-eabi` 4.4.0.20231231-2) |
| QEMU (user and system) | 8.2.2 (Debian 1:8.2.2+ds-0ubuntu1.18) |
| MicroPython (unix port) | 1.22.1 (Ubuntu package `micropython` 1.22.1+ds-1build2, built 2024-04-01) |
| AIL | commit `dd878bf` (the branch base, `origin/integ`) |

All tools come from Ubuntu apt; nothing is fetched from the network by `run.py`.

## Method

**AIL C emission.** `AIL_CURRENT/ail_chatgpt.py compile prog.py --syntax python -o exe
--debug-dir DIR` leaves the generated C in `DIR/program.c`. That single file embeds only the
runtime the program actually reaches. `run.py` compiles that C with

```
-O2 -fno-tree-slp-vectorize -ffp-contract=off -fopenmp-simd -fno-asynchronous-unwind-tables   (AIL's own flags)
```

for every target, plus `-lm`. (AIL's three `-Werror=` diagnostic flags are left out; they change no
code.) The native row is `gcc` on that same `program.c`, not AIL's own `compile -o exe` binary.

**Linux ARM targets.** `aarch64-linux-gnu-gcc` and `arm-linux-gnueabihf-gcc`; run under
`qemu-aarch64 -L /usr/aarch64-linux-gnu` and `qemu-arm -L /usr/arm-linux-gnueabihf`.

**Bare metal.** Cortex-M3 on QEMU `mps2-an385` (4 MiB SRAM at 0x20000000): newlib-nano
(`--specs=nano.specs`), librdimon semihosting (`--specs=rdimon.specs`), `harness/startup.c`
(vector table, reset path, semihosting exit), `harness/mps2_an385.ld`, and `harness/memcount.c`
(a `--wrap=malloc` counting allocator; the peak is printed to stderr after `main`). Float output
needs `-u _printf_float` because newlib-nano's `printf` has no float formatter by default. The
program is compiled at `-O2` like the Linux targets.

**Jitter.** 20 000 iterations at a 1 ms period. Each iteration, in every language, runs the same PID
update (8 doubles: `0.85*err + 0.12*integral + 0.04*deriv`, clamped, `state += (u - 0.3*state)*0.005`),
then sleeps to the next absolute deadline, then records `now - deadline` in microseconds into a
1 us histogram. `p50/p99/p99.9` are nearest-rank from that histogram; `max` is exact (rounded to the
nearest microsecond in the table). "Overruns"
counts periods whose wake-up was at least one full period (1000 us) late. `noalloc` keeps all state
in preallocated lists; `alloc` additionally copies the 8-element state list every iteration
(`malloc`/`free` in C, `list(state)` in AIL and MicroPython). C uses
`clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME)`; AIL has no `clock_nanosleep`, so it keeps an
absolute deadline in `time.perf_counter()` seconds and calls `time.sleep(remaining)`; MicroPython
keeps the deadline in `time.time_ns()` and calls `time.sleep_us()`. Three repetitions are run and
the median of each metric is reported. The runner is a shared GitHub Actions VM: the C row is the
noise floor, not an absolute guarantee.

**RAM.** Peak RSS of the process (`/usr/bin/time -f %M`) for native and for the qemu runs (the qemu
number includes the emulator, so it is an upper bound). Bare-metal heap high-water comes from the
counting allocator.

## Files

```
progs/pid.py            PID controller over a fixed 8-element list, prints final state
progs/ringbuf.py        fixed sensor ring buffer, moving average
progs/kin2.py           2-link arm forward kinematics, math.sin/cos, 10000 angles
progs/pid.c             1 kHz jitter loop, C
progs/pid_ail.py        1 kHz jitter loop, AIL (compiled by AIL)
progs/pid_mpy.py        1 kHz jitter loop, MicroPython unix port
progs/census/*.py       one OS subsystem each, for the bare-metal blocker census
harness/startup.c       Cortex-M vector table, reset path, semihosting exit
harness/mps2_an385.ld   QEMU MPS2-AN385 linker script
harness/memcount.c      counting allocator (--wrap=malloc), heap high-water
run.py                  builds, runs and writes results.json
results.json            every measurement
```
