# job job-ffembed2-11070326  started 2026-11-06T18:29:53Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Committed as `7fa96df`. Final report:

## ffembed2 — what landed

**Numbers:** 3 callers × 4 examples = **12/12 match CPython** (C static, Rust, ctypes/shared). Threads: **2 × 500 = 1000/1000 correct**, clean under `-fsanitize=thread`.

**Changes** (only permitted files):
- `ail_embed.py`: `--shared` → `lib<name>.so` from a `-fPIC` object; `--cc` now accepts a full command (needed for TSan); every export + `init`/`shutdown` takes one process-wide `pthread_mutex`, released on all return paths (success, status 1, status 2).
- `examples/embed/<case>/rust/`: `Cargo.toml` (no deps), `build.rs` (finds repo root, runs `ail_embed.py`, emits link directives), `src/main.rs` (`extern "C"`).
- `examples/embed/<case>/use_ctypes.py`: loads the `.so`, calls each export, compares every value with `mod.py` imported directly; builds the `.so` itself unless `--lib` is given.
- `examples/embed/README.md`, `AIL_CURRENT/test_ail_embed.py` (+ manifest `1b.txt`).

**Thread decision:** the typed path has no lock (the general path's `threadrt.py` GIL is only for `crthread`-style programs), and its exception stack/arena/error are globals → the wrapper's mutex is the AIL lock; second call waits. `last_error()` is unlocked and documented as valid only until the next call.

**Probes** (`/tmp/probes/`), all run and compared with `python3 abi.py`:
| probe | result |
|---|---|
| `abi_driver.c` + static `libabi.a` | same stdout, exit 0 |
| `abi_driver.c` + shared `libabi.so` | same stdout, exit 0 |
| `abi_ctypes.py` + `.so` | same stdout; 1000/1000 threaded ctypes calls |
| `AIL_UNIFIED_FORCE=1` build | refused by name (general path), same as before this change |
| `cmp.sh abi.py` (default and forced-unified) | both "same stdout" |

Values covered: 0, −1, INT64_MIN/MAX, negative modulo path, `bool`, `float`, empty/unicode strings, embedded NUL in both `str` and `bytes`, and the status-2 short buffer.

**Tests:** `test_ail_embed` OK (7 tests; Rust skips without cargo — verified with `PATH` stripped; TSan skips under `ulimit -v`). TSan run without the cap: no report; removing the lock from the wrapper makes it report 8 races (`ail_exc_top`, `ail_exc_cleanup`, `ail_embed_in_call`, `ail_embed_saved_*`, `ail_embed_error`), so the test has teeth. `test_ail_files` OK (18, 1 skip), `test_ail_corpus_findings3` OK. `test_ail_safetynet` passes without a memory cap; under `ulimit -v 1500000` the `S4_generators_gc` case stops after its first line — I reproduced it standalone without the cap and it matches CPython, so it is the 1.5 GB cap, not this change.

Not pushed: the runner instructions for this session say to commit on the branch and not push, so I did not open the PR or wait on shards.
[commandcode stop=end_turn turns=77 out_tokens=54139]

## review 0
[model commandcode/deepseek-v4.1-flash]
I have everything I need. Here's my report.

## What the diff really does

`ail_embed.py` gains `--shared` (link a `.so` from the existing `-fPIC` object instead of `ar`), turns `--cc` into a shlex-split command list, and wraps every generated export plus `init`/`shutdown` in one static `pthread_mutex` (unlocked on success, status 1 and status 2). The rest is four new no-dependency Rust callers (`Cargo.toml`/`build.rs`/`src/main.rs`) and four `use_ctypes.py` scripts, README + `test_ail_embed.py`. This matches the report's description; nothing undeclared.

## Probes (mine, /tmp/rprobes)

| probe | covers | result |
|---|---|---|
| `lockleak_fib.c` | out=NULL, `len=SIZE_MAX`, then call again | no hang; `after-null 0 55`, `after-toolong 0 55`; exit 0 |
| `lockleak_raiser.c` | status 1 (ValueError), out=NULL, call again | no hang; `after-err 0 3`, `after-null 0 5` |
| `lockleak_transform.c` | status 2 short cap, cap=0, empty, call again | no hang; `after-short 0 len 3 [ABC]`, `empty 0 len 0` |
| `threads_transform.c` | 2 threads × 500, differing str lengths | `1000/1000`, exit 0; same under `-fsanitize=thread` (0 reports) |
| `ctypes_edge.py` | .so: fib 0/1/2/91/92/93-overflow, gcd ±INT64_MIN/MAX, empty/unicode/embedded-NUL str, cap = n, n+1, 0, 3 | 0 mismatches vs `mod.py` |
| `alias.c` | in-place `out==in`, mutate input after call, reuse buffer | `inplace 0 len 3 [ABC]`, `kept [AB] new [ZZ]`, `reuse [C]` (static and .so) |
| plain `program.c` base vs HEAD | non-user program | byte-identical |
| `--shared` edges | `--name`, rebuild, general-path source | `libcustom.so`, exit 0; refusal by name |

Callers: C 4/4, Rust 4/4 (`cargo build --release --offline`), ctypes 4/4 — all equal to `python3 mod.py` (12/12 verified independently).

## Tests on HEAD

`par_check.py -j 2 test_ail_embed test_ail_safetynet` under `ulimit -v 1500000`: `test_ail_embed` OK (7 tests, TSan skipped under the cap — as reported); `test_ail_safetynet` failed only `S4_generators_gc`. I built that case with both compilers: HEAD and base print the identical wrong text (`AIL internal error: generator: no stack`) under the cap — pre-existing. `update_manifest.py --check` passes; only permitted paths changed.

## Report claims

- 12/12 match CPython — **verified**.
- 1000/1000 two-thread correct; TSan clean — **verified** (own probe; TSan skip under `ulimit -v` also confirmed).
- `--shared` from a `-fPIC` object; `--cc` takes a full command — **verified** (`"gcc -O2"`, `"gcc -fsanitize=thread"`).
- Lock taken by every export/`init`/`shutdown`, released on success/status 1/status 2 — **verified** (read + no-hang probes on every error path).
- `test_ail_embed` 7 tests, Rust skips without cargo — **verified** for 7 tests/skip logic; the no-cargo skip itself not exercised (cargo present).
- `test_ail_files` / `test_ail_corpus_findings3` OK — **unverified** (outside my run set).
- "S4 stops after its first line" — **verified in substance** (cap artifact, identical on base) but the wording is loose: it prints an `AIL internal error:` line, not just a short stdout.
- "8 races without the lock" — **unverified** (not going to edit source).
- "Not pushed / no PR / no shards" — **confirmed** by branch state; a process gap only.

Minor, non-blocking: the static lib and Rust link now need pthread; `build.rs` does not emit `rustc-link-lib=pthread`, which works only where pthread lives in libc (glibc ≥ 2.34 — true here). `last_error()` stays unlocked, so it is a real UAF race if called concurrently — but the README defines that contract explicitly.

## Pre-existing

- `len = SIZE_MAX` gives status 1 with `RuntimeError: unknown error` instead of `OverflowError: …` (identical on `/tmp/base`).
- `S4_generators_gc` under `ulimit -v 1500000` (identical on `/tmp/base`).

Speed: not applicable — a non-user program's `program.c` is byte-identical base vs HEAD, so gdev instruction counts cannot change.

VERDICT: ACCEPT
[commandcode stop=end_turn turns=28 out_tokens=27801]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-06T20:12:33Z
