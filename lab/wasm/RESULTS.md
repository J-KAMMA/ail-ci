# AIL on wasm32-wasi (ffwasm1, 2026-11-06; ffwasm2, 2026-11-08)

## ffwasm2 (2026-11-08): WASI refusals, remaining tasks, sizes

This run re-fetched the pinned toolchain from the official sources and re-measured everything. Both archives match the
sha256 recorded under ffwasm1 (zig 0.17.1 `3581863e...b17a`, wasmtime 50.0.1 `68546645...98a5`), so the numbers below
were produced on this runner, not copied from ffwasm1.

Refusals by name (no linker error), each with a `write instead:` line, checked with `AIL_TARGET=wasi`:
- `import subprocess` -> `subprocess is not available on wasm32-wasi: WASI has no process creation (no fork/exec)`
  (proclib.py; `AIL_TARGET=wasi`, or `AIL_TARGET_OS=wasi`). Exit 3, `not in the subset:` prefix.
- `import threading` / `queue` / `concurrent.futures` -> `... is not available on wasm32-wasi: WASI has no threads`
  (threadlib.py). Exit 2.
- `import socket` / `signal` -> the same shape from `tools/wasm_build.py` (`WASI_REFUSED`), checked before the
  toolchain so the build fails with the name even when zig is missing. It also catches the threaded patterns
  `typedpar.py` lowers before threadlib.py sees the import. There is no socklib.py or siglib.py in this tree, so the
  build script is the refusing layer for those two; without it `ail_chatgpt.py compile` falls back to the general path
  and the failure would only appear at link time.
- The `WASI_REFUSED` scan resolves each import through `ail_modules.Program.local_top`, so an `import signal` that
  names a sibling `signal.py`, a package directory, an `AIL_PATH` module or a bundled module is left to the compiler:
  it is an ordinary local module, not the standard one, and still builds. Only the standard module is refused.
- `tools/wasm_build.py` runs the host compiler with `AIL_TARGET_OS=wasi`, not `AIL_TARGET=wasi`: the latter would make
  `sys.platform` unknown in `ail_modules.py` until `TARGETS['wasi']` exists.

Remaining tasks: none. The ffwasm1 table's 10/10 is re-verified below. The build carries
`-D_WASI_EMULATED_PROCESS_CLOCKS` and the test's `--dir D::D` preopens; `clock_gettime` and file preopens work (the
tasks read files and stdin).

Deep recursion (the one real bug found by running the new test): AIL's typed path stops at
`AIL_MAX_RECURSION_DEPTH` (50000 frames) and the general path at a real-stack check against a 256 MiB
`AIL_STACK_UNLIMITED` budget, so the module needs a 256 MiB stack (`-Wl,-z,stack-size=268435456`). But wasmtime's
**native** execution stack (`-W max-wasm-stack`, default under 1 MiB) is separate from that linear-memory stack, and it
trapped with `wasm trap: call stack exhausted` before either check fired. `WASMTIME_FLAGS` now sets
`-W max-wasm-stack=268435456`, matching the linear budget, so the program reports `RecursionError` instead. Verified
(typed, auto-typed, and `AIL_UNIFIED_FORCE=1` general path): `f(50000000)` exits nonzero with
`RecursionError: maximum recursion depth exceeded` on stderr and no "call stack exhausted"; `f(49000)` still computes.
`test_deep_recursion_is_loud` covers all three paths.

**Run with `-W max-wasm-stack=268435456` (part of `WASMTIME_FLAGS`)** or a deep recursion traps without a message.

## Size table (ffwasm2, this run)

`.wasm` bytes per compare-lab task, standard build (`zig cc ... -O2 ... -s`). `-s` already strips: the same program is
921,159 bytes without it and 7,424 with it, so these numbers are stripped. `wasm-strip` is not installed, and is not
needed. The Rust side is **not measured**: `rustup target list --installed` lists only `x86_64-unknown-linux-gnu`, no
`wasm32-wasip1`, and the task says to record that and stop rather than install the target.

| task | cases matching | `.wasm` bytes |
|---|---|---|
| berth_sim | 27/27 | 75,658 |
| chain_relax | 33/33 | 47,310 |
| echo_pack | 58/58 | 47,087 |
| ledger_bin | 56/56 | 76,029 |
| rail_transfer | 25/25 | 78,854 |
| scar_life | 54/54 | 53,841 |
| tally_lang | 76/76 | 114,989 |
| term_rank | 44/44 | 92,043 |
| ticket_audit | 92/92 | 217,375 |
| tree_fold | 56/56 | 76,584 |

**10/10 build, 10/10 match** on every public, hidden and perf case (stdout and exit status vs
`tasks/<task>/reference.py` under CPython 3.12). Geomean size 79,097 bytes; total 879,770 bytes. Sizes differ a few
percent from the ffwasm1 column because the runtime changed between snapshots; the match counts are unchanged.
No linker error and no trap without a message remains.

## ffwasm1

`tools/wasm_build.py SRC -o OUT.wasm` runs the host compile (`ail_chatgpt.py compile SRC --debug-dir WORK/c`), takes
`WORK/c/program.c` and builds it with `zig cc -target wasm32-wasi -O2`, force-including `tools/wasm_shim.h`. Run it
with `wasmtime run -W exceptions=y [--dir D::D] OUT.wasm ARGS`. `AIL_CURRENT/test_ail_wasm.py` builds and runs hello,
try/except and three tasks (chain_relax, tally_lang, tree_fold, public cases; tree_fold goes through the size_t workaround); it is skipped without zig or wasmtime.

Toolchain (official downloads, sha256 of the archive):
- zig 0.17.1 `zig-x86_64-linux-0.17.1.tar.xz` 3581863e3cbcfd0fce0efc682ce7e9e93da96668a977791d356a26d2a7e9b17a
- wasmtime 50.0.1 `wasmtime-v50.0.1-x86_64-linux.tar.xz` 685466455dd42a14774a86c36c8f2e45cbb9bd6d92a850139315df60a75498a5

zig 0.13.0 with wasmtime 27.0.0 was tried first. It runs hello (7,619 bytes), but it has no usable setjmp: zig 0.13
uses LLVM 18 legacy EH, and wasmtime 27 runs no EH at all. Every try/except then fails (tally_lang's parse-error case),
so the measurement uses 0.17.1/50.0.1. setjmp/longjmp come from wasi-libc on the exception-handling proposal
(`-mexception-handling -mllvm -wasm-enable-sjlj -mllvm -wasm-use-legacy-eh=false`). The shim defines the
`__c_longjmp` tag, because no library in zig's wasi-libc defines it. Emulated signal, mman and process-clock libraries
are linked. The general path needs mmap; without `-D_WASI_EMULATED_MMAN` it is a compile error.

## Compare-lab tasks (`lab/compare/src/<task>/typed.py`, default build)

Oracle: `tasks/<task>/reference.py` under CPython 3.12. Cases: every public and hidden case of `gen.py` plus the perf
case. Compared: stdout and exit status. Time: wall seconds, median of 3, on the perf input, wasmtime against the native
gcc -O2 binary from the same compile. GitHub runner, 4 cores.

| task | built | cases matching | first difference | .wasm bytes | native s | wasmtime s |
|---|---|---|---|---|---|---|
| berth_sim | yes | 27/27 | - | 74,358 | 2.339 | 4.418 |
| chain_relax | yes | 33/33 | - | 46,569 | 1.255 | 1.208 |
| echo_pack | yes | 58/58 | - | 46,505 | 0.998 | 1.990 |
| ledger_bin | yes | 56/56 | - | 75,133 | 0.842 | 1.256 |
| rail_transfer | yes | 25/25 | - | 76,553 | 0.070 | 0.121 |
| scar_life | yes | 54/54 | - | 52,886 | 29.787 | 38.019 |
| tally_lang | yes | 76/76 | - | 113,847 | 1.377 | 2.677 |
| term_rank | yes | 44/44 | - | 90,860 | 2.319 | 2.916 |
| ticket_audit | yes | 92/92 | - | 215,930 | 1.700 | 3.811 |
| tree_fold | yes | 56/56 | - | 80,354 | 1.456 | 2.839 |

**10/10 build, 10/10 match** on every public, hidden and perf case. No task prints wrong output.

The first run matched only 6/10. The other 4 stopped with `MemoryError: out of memory` before printing anything,
and all 4 failures had one cause: `read_stdin_bytes(1 << 40)` on a 32-bit `size_t`. The typed runtime's reader
(`ail_stdin_fill_bytes`) does `if (next > (size_t)size) next = (size_t)size;`, which truncates 2^40 to 0, so the
first buffer was `realloc(buf, 0)`. zig's wasi-libc returns NULL there, which raised MemoryError. The same cast in
`if (n == (size_t)size) break;` would end a read of 2^32+5 bytes after 5 bytes. wasm64 is not an option: zig 0.17.1
ships no wasm64-wasi libc.

**Workaround in the build, not in the emitter:** `tools/wasm_build.py` (`patch_c`) writes a copy of the C,
`WORK/c/program.wasm.c`, with one line added at the start of `ail_stdin_fill_bytes`:
`if ((uint64_t)size > (uint64_t)SIZE_MAX) size = (int64_t)SIZE_MAX;`. A read on wasm32 cannot return more than
SIZE_MAX bytes, so the result is still what Python returns. `program.c` and the host binary are not changed. If a
program's C has no reader, it is built as it is (the 6 tasks above build to the same bytes as before). If the reader
exists but no longer has the expected shape, the build stops loudly instead of building without the patch. The
rows for echo_pack, scar_life, term_rank and tree_fold are new measurements on the patched C. The other 6 rows are
from the first run; this run re-checked their match counts and bytes, but not their times.

**Follow-up (emitter, one line):** move this saturation into `ail_stdin_fill_bytes` in `cruntime.py` (no-op on 64-bit
hosts, so the C is the same there), then delete `patch_c`. Audit the other `(size_t)<int64>` casts for 32-bit targets
in the same pass (for example the file and socket reads near `cruntime.py:27695` and `:28196`, which no task here
uses).

First run, before the workaround: with `AIL_UNIFIED_FORCE=1` (general path), the same 4 tasks matched on every public and hidden case: echo_pack 57/58,
scar_life 53/54, term_rank 43/44, tree_fold 55/56. Only the perf input fails: an out-of-memory stop (echo_pack,
tree_fold; wasm32 has 4 GiB) or more than 60 s (scar_life, term_rank). Those .wasm files are 545-702 KB.

## Probes (/tmp/probes, wasm against CPython and against the native binary, default and AIL_UNIFIED_FORCE=1)

Probe | result
---|---
hello, try/except (`exc.py`, `exc2.py`: ZeroDivisionError, KeyError, IndexError, finally, attribute and dict values, uncaught `int("x7")`) | match, both builds
`stdin_text.py` (sys.stdin.read), `files.py` (open via `--dir`, dict counts), `big.py` (2^40 arithmetic, int64 edges, 200 KB strings) | match, both builds
`ints.py` (int beyond int64 from text and from `+`) | matches the native AIL binary (loud OverflowError, AIL's int64 rule), not CPython: same as the host
`rsb.py` (`read_stdin_bytes(1 << 40)`) | first run: MemoryError in the default build (the gap above); now matches, both builds

Probes for the size_t workaround (`/tmp/probes/r`, 200 KB of stdin, CPython against the wasm build and the native
binary, default build and `AIL_UNIFIED_FORCE=1`):

Probe | result
---|---
`rsb_big` (1 << 40 at top level), `rsb_loop` (1 << 40 in a loop until EOF), `rsb_small` (5, then 0) | match, both builds
`rsb_wrap` ((1 << 32) + 5, which the cast would truncate to 5) | match, both builds (default: patched C)
`rsb_vals` (3 from a list item, 1 << 33 from an attribute, 1 << 34 from a list item, 1 << 62 from a dict value, all passed as an argument) | match, both builds (default: patched C)
`rsb_neg` (`read_stdin_bytes(-1)` in try/except ValueError) | default: match. `AIL_UNIFIED_FORCE=1`: **prints nothing where CPython prints `ValueError`**, and the host native binary does the same (`~/tools/cmp.sh` shows the same diff), so this is a bug in the host general path, not in the wasm build. Reported here, not fixed: it is outside this task's files

## Not done / follow-ups

- `--target wasi` in `ail_chatgpt.py` (hook: compile to C, then this script's zig step). `sys.platform` and `os.name`
  are folded for the host (`linux`/`posix`), not `wasi`. That matches the CPython-on-host oracle used here, but
  `TARGETS['wasi'] = ('wasi', 'posix')` in `ail_modules.py` is needed once the flag exists. It is not added now
  because nothing selects it.
- `lab/stdlib/*/` programs are not measured in this run.
- Subprocess, threads and signals were not exercised: none of the 10 tasks uses them.
