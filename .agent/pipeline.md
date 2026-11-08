# job job-ffwasm2-11081519  started 2026-11-08T06:20:22Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. Summary:

**Sub-step 1 — WASI refusals by name** (verified with `AIL_TARGET=wasi`)
- `import subprocess` → exit 3, `subprocess is not available on wasm32-wasi: WASI has no process creation (no fork/exec)` + `write instead:`
- `import threading`/`queue`/`concurrent.futures` → exit 2, `... wasm32-wasi: WASI has no threads` + `write instead:`
- `import socket`/`signal` → refused by `tools/wasm_build.py` `WASI_REFUSED` before the toolchain check (no socklib/siglib exist). `ail_chatgpt.py` alone falls back to the general path, so the build layer is the correct refusal point.

**Sub-step 2 — remaining tasks + deep recursion (real bug found and fixed)**
Re-fetched pinned zig 0.17.1 and wasmtime 50.0.1 (sha256 match the recorded values) and re-ran everything. The new deep-recursion test exposed a genuine failure: wasmtime's native `max-wasm-stack` (default <1 MiB) is separate from the module's 256 MiB linear stack, so `f(50000000)` trapped with `call stack exhausted`. Added `-W max-wasm-stack=268435456` to `WASMTIME_FLAGS`; typed, auto-typed and `AIL_UNIFIED_FORCE=1` general path now all print `RecursionError`, and `f(49000)` still computes. Test extended to all three paths.

**Sub-step 3 — size table**
All 10 compare-lab tasks: **10/10 build, 10/10 match** on public+hidden+perf. Fresh stripped `.wasm` sizes recorded in `RESULTS.md` (geomean 79,097 B, total 879,770 B). `-s` already strips (921,159 → 7,424 B test). Rust column unmeasured: `rustup target list --installed` lacks `wasm32-wasip1`; `wasm-strip` absent.

**Probes** (`/tmp/probes`): `host_sub`, `host_exc`, `host_rec` match CPython on both builds; wasm `deep/deepu/mid/midu` and general-path `deepg/midg` give `RecursionError` or correct counts; refusal probes for all four modules.

**Tests on final commit:** `test_ail_wasm` 11 OK · `test_ail_subprocess` 23 OK · `test_ail_files` 18 OK · `test_ail_corpus_findings3` 2 OK · `test_ail_safetynet` 5 OK · `test_ail_threads` 18 OK. Manifest `--check` clean.

Note: per the job rule ("do not push") I committed on `job-ffwasm2-11081519` (`8e9ce80a`) but did not push or open the PR, so the 20 CI shards were not run here. Running `test_ail_wasm` under `ulimit -v` fails because zig needs more address space; it passes uncapped.
[commandcode stop=end_turn turns=58 out_tokens=38725]

## review 0
[model commandcode/deepseek-v4.1-flash]
All background jobs are done. Here is my report.

## What the change really does

`tools/wasm_build.py` refuses 7 import names by scanning the *source text* before compilation; `proclib.py`/`threadlib.py` add env-gated (`AIL_TARGET[_OS]=wasi`) refusals; the wasm build's linear stack grows 8 MiB → 256 MiB and `WASMTIME_FLAGS` gains `-W max-wasm-stack=268435456`; tests and `RESULTS.md` updated. This matches the report's description, except that "socket/signal refused" is only true for the `wasm_build` layer (the compiler alone accepts them), which the report does disclose.

## Probes (`/tmp/rprobes/`, HEAD unless noted)

| probe | result |
|---|---|
| `rv_plain` / `rv_sub_host` / `rv_sub_alias` / `rv_thread_host` / `rv_queue_host` (host, both builds) | match CPython; C byte-identical to `/tmp/base` for all five |
| `wasi/s1,s2,s3` subprocess (`import`, `from`, `as`) under `AIL_TARGET` and `AIL_TARGET_OS` | refused by name, exit 3, `write instead:` present |
| `wasi/s4,s5` threading, `s6` queue, `s7` concurrent.futures, `s8` concurrent | refused by name, exit 2 |
| `wasi/s1,s4,s6,s9,s10` via `tools/wasm_build.py` | refused by name before the toolchain; `s15_plain` builds (3,895 B) |
| deep recursion typed / auto-typed / `AIL_UNIFIED_FORCE=1` | `RecursionError`, exit 1; `f(49000)` → `49000`; without `max-wasm-stack` it traps rc=134 (flag is necessary) |
| `biglist`, `fact` | `1000000 0`, `2432902008176640000` — new stack size harmless |
| all 10 compare-lab builds | 10/10 build; sizes match `RESULTS.md` exactly (total 879,770 B, geomean 79,097 B) |

## Claims

- Verified: 10/10 build; per-task sizes/geomean/total; subprocess exit 3, threading exit 2, `write instead:`; deep recursion loud on all three paths and `f(49000)`; `rustup target list --installed` lacks `wasm32-wasip1`; `wasm-strip` absent; zig 0.17.1 / wasmtime 50.0.1; `update_manifest.py --check` clean; `test_ail_wasm` 11 OK and `test_ail_safetynet` OK (uncapped).
- Unverified: "10/10 match on public+hidden+perf" (I verified the 3 tasks `test_ail_wasm` covers plus all builds; my all-tasks perf run was stopped at the time box). `test_ail_subprocess`/`test_ail_threads`/`test_ail_files` counts and the `921,159 → 7,424` strip figure were not re-run.

## Pre-existing (identical on base)

- wasmtime cannot start *any* module under `ulimit -v 1500000` ("Cannot allocate memory os error 12"), base and HEAD alike.
- Under `ulimit -v 6000000` the `-j 2` pair failed `test_try_except`/`test_task_tally_lang`; both pass individually and the pair passes uncapped. Environmental, not change-caused.

## Defect

1. **The source-text refusal ignores local module shadowing**, so a legitimate program that the base built and ran is now refused. `wasi_refusal()` in `tools/wasm_build.py` rejects any top-level `import <name>` without checking whether `<name>` is a sibling module; the compiler itself supports shadowing (`ail_modules.is_local_import`; it prints `note: signal.py shadows the standard library module signal`).

   Probe `/tmp/rprobes/multi2/local/signal.py`:
   ```python
   def v():
       return 41
   ```
   `/tmp/rprobes/multi2/local/main.py`:
   ```python
   import signal
   print(signal.v())
   ```
   Expected (base, `/tmp/base/tools/wasm_build.py main.py`): build succeeds, wasmtime prints `41`, exit 0.
   Actual (HEAD, `tools/wasm_build.py main.py`): exit 1, `signal is not available on wasm32-wasi: WASI has no POSIX signals.`

   Same class for a local `subprocess.py` / `threading.py` / `queue.py` / `socket.py` / `concurrent.py` / `multiprocessing.py`. Fix: skip names with a sibling `<name>.py`/`<name>.ail`, or reuse the compiler's local-import test.

Speed: the change is compile-time only and leaves generated C byte-identical (verified for plain, subprocess, threading and queue programs), so no instruction-count run was needed.

VERDICT: FIX
1. `tools/wasm_build.py:wasi_refusal()` refuses imports that resolve to a local module. Probe `/tmp/rprobes/multi2/local/{main.py,signal.py}`: expected build OK and output `41` (base does this); actual exit 1 with `signal is not available on wasm32-wasi`. Honour local shadowing as the compiler's own checks do.
[commandcode stop=end_turn turns=48 out_tokens=44471]

## worker report 1
[model commandcode/deepseek-v4.1-flash]
All checks are green. Final state:

## Fix

`tools/wasm_build.py` `wasi_refusal()` now resolves each candidate import through the compiler's own `ail_modules.Program.local_top` (the same search path: entry dir, `AIL_PATH`, bundled stdlib) and refuses only when the name is *not* local. One defect fixed: a sibling/`AIL_PATH`/package module with a refused name (`signal.py`, `threading.py`, …) is no longer refused; genuine standard-module imports still are. Signature is `wasi_refusal(text, src=None)`; `build()` passes the resolved path.

Also added: `RESULTS.md` bullet documenting the resolution rule; two tests in `test_ail_wasm.py` (unit: sibling file/package/alias/from, both directions; end-to-end: `signal.py` beside `main.py` builds and prints `41` under wasmtime). Manifest refreshed.

## Probes (`/tmp/probes`, all on HEAD = bdfffd7d)

| probe | result |
|---|---|
| `shadow_{subprocess,multiprocessing,threading,queue,concurrent,socket,signal}/main.py` + sibling `<m>.py`, wasm build + wasmtime | build OK, `41`, rc 0 (7/7) |
| `shadow_pkg` (`signal/__init__.py`) | build OK, `41`; host build and `AIL_UNIFIED_FORCE=1` both `41` = CPython |
| `ailpath_main.py` + `AIL_PATH=/tmp/probes/ailpathlib/signal.py` | build OK, `41` |
| `gen_<m>/main.py` for all 7 names, no local module | rc 1, `<m> is not available on wasm32-wasi: WASI has no …`, `write instead:` present (7/7) |
| reviewer's `/tmp/rprobes/multi2/local` shape | reproduces fixed: build OK, wasmtime `41` |
| all 10 `lab/compare/src/*/typed.py` wasm builds | 10/10 build; total 879,770 B, matches `RESULTS.md` |

Note: local `threading.py` differs from CPython on the *host* too (CPython preloads `threading` at startup, so its sibling is ignored and `threading.v()` raises) — pre-existing compiler-local-module behaviour, unchanged by this diff; `signal`/`socket`/`queue`/`subprocess` shadows match CPython both builds.

## Tests (final commit)

- `test_ail_wasm.py`: 13 tests OK (includes the 2 new ones)
- `test_ail_safetynet.py`: 5 OK · `test_ail_files.py`: 18 OK · `test_ail_corpus_findings3.py`: 2 OK
- `update_manifest.py --check`: clean

Committed as `bdfffd7d` on `job-ffwasm2-11081519`; not pushed (job rules forbid push). CI shard checks therefore not run/watched.
[commandcode stop=end_turn turns=37 out_tokens=13065]

## review 1
[model commandcode/deepseek-v4.1-flash]
**What the diff really does** (one line): adds build-time WASI refusals for `subprocess`/`threading`/`queue`/`concurrent`/`multiprocessing` (compiler, `proclib.py`/`threadlib.py`) and for `socket`/`signal` (an AST scan in `tools/wasm_build.py`, resolving each name through `ail_modules.Program.local_top`), sets `AIL_TARGET_OS=wasi` for the wasm host compile, raises the wasm linear stack to 256 MiB and wasmtime's native stack to match, plus tests and RESULTS notes. The report's "Fix" headline describes only the final commit (`bdfffd7d`); the diff is the whole sub-step 1–3 work. Nothing else differs.

**Probes** (`/tmp/rprobes/rev`, `cmp.sh`-style plus `tools/wasm_build.py` + wasmtime 50.0.1 / zig 0.17.1)

| probe | result |
|---|---|
| `sh_{subprocess,threading,signal,socket,queue,concurrent,multiprocessing}/main.py` + sibling module, wasm build + run | 7/7 build, print `41`, rc 0 |
| `sh_pkg` (`signal/__init__.py`), `qimp` (`from signal import v`), `pkgimp` (`import pkg.signal`), `apmain` (`AIL_PATH`) | build, `41` |
| CPython on same sources | `41` for all except `threading` (AttributeError — pre-existing, as the report notes) |
| `ref_{subprocess,threading,signal,socket}`, `gen/{queue,concurrent,multiprocessing,fromq}` | refused by name, `write instead:` present; subprocess rc 3, threading rc 2 (matches RESULTS.md) |
| `helper/` where `helper.py` imports subprocess (transitive) | refused by name via the compiler |
| default-build C for `subprocess`, `threading`, `queue` programs, HEAD vs `/tmp/base` (`--debug-dir`) | byte-identical (distinct=1) |
| `AIL_TARGET_OS=wasi` effect on C (plain, echo_pack) | C byte-identical with/without the env var |
| deep recursion typed / untyped / forced-general / 30-locals-per-frame / try-inside, `f(50000000)` | nonzero, `RecursionError: maximum recursion depth exceeded`, no trap; `f(49000)` → `49000`; base has no such check |
| all 10 `lab/compare/src/*/typed.py` wasm builds | 10/10, sizes match RESULTS.md exactly, total 879,770 B |
| echo_pack / tree_fold / ticket_audit, all public+hidden+perf cases vs `reference.py` | 58/58, 56/56, 92/92 match (ticket_audit needs `--dir /`) |

**Report claims**: all verified — local resolution (sibling/package/`AIL_PATH`/alias/`from`), genuine refusals by name for all four required modules plus queue/concurrent/multiprocessing, 7/7 shadow builds, 10/10 lab builds and the exact byte table, 13 tests in `test_ail_wasm.py`, manifest clean, not pushed. Only nuance: `socket`/`signal` are refused by the build script, not the compiler (report says so).

**Tests** (HEAD): `test_ail_wasm.py` 13 OK, `test_ail_safetynet.py` OK, `test_ail_files.py` 18 OK, `test_ail_corpus_findings3.py` 2 OK.

**Pre-existing** (identical on `/tmp/base`, not blocking): (1) under `ulimit -v 1500000` wasmtime cannot instantiate *any* module (4.36 GB address reservation), so all `WasmTests` fail with `mmap failed to reserve 0x104000000`; base `test_hello` fails the same way. (2) host shadow of `threading` differs from CPython (report documents it). (3) a transitive `import socket` in a local helper is not WASI-named; unused it builds and prints the same as base, used it hits the pre-existing `socket.gethostname (not yet published …)` refusal — same on base.

**Speed**: no runtime code changed; default-build C is byte-identical for programs using the feature and for plain ones, so no icount run was needed.

**Unverified**: full case sets for the other 7 lab tasks (builds and sizes verified); `test_ail_safetynet`'s test count (module passed).

VERDICT: ACCEPT
[commandcode stop=end_turn turns=70 out_tokens=42814]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-08T10:05:52Z
