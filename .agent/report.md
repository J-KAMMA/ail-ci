# job job-ffcrate2-11061044  started 2026-11-06T01:47:20Z  worker=chain reviewer=chain (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Implemented and committed as `5a32332` (not pushed; the job rules forbid push/PR).

**Added 4 crates in `examples/crate/`**
- `wordbag/` — `Handle("bag", free="wordbag_free")`, add/count/free, plus `wordbag_bump`/`wordbag_seed`
- `slugify/` — caller buffer, negative needed size when too small
- `walk/` — module-level callback per step, exception propagation
- `bits/` — offline dependency vendored at `bits/vendor/tinydep/`

**Measurements (median of 3)**

| crate | AIL bytes | AIL time | CPython time |
| --- | ---: | ---: | ---: |
| wordbag | 5,439,640 | 0.9 ms | 51.6 ms |
| slugify | 5,424,984 | 0.9 ms | 51.0 ms |
| walk | 52,552 | 0.8 ms | 53.8 ms |
| bits | 23,456 | 0.7 ms | 49.8 ms |

All 7 crate examples now match CPython stdout/exit status.

**Probes** (`~/tools/cmp.sh`, default + general builds)
- `wordbag_basic`, `slugify_edges`, `walk_callback`, `bits_values`: same stdout as CPython on both builds.
- `wordbag_huge`: CPython prints `9223372036854775813`; both AIL builds stop loudly with `OverflowError: integer overflow in +`. Documented as limitation 4 in the README; default example avoids it.

**Tests:** 38 passed, 1 skipped (`test_ail_examples_crate`, `test_ail_cargo`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`). Manifest `--check` passes. The safetynet S4 GC case needs more than the 1.5 GB virtual cap; it passes without that cap.
[cost $0.0000, opencode tokens {"total": 7025381, "input": 152972, "output": 21888, "reasoning": 29017, "cache.write": 0, "cache.read": 6821504}]
    tool time: bash 19.8 min, write 0.0 min, edit 0.0 min, read 0.0 min
        468s bash   export PYTHONPATH=$PWD/AIL_CURRENT PYTHONDONTWRITEBYTECODE=1; ulimit -v 1500000; python3 -B -m unittest AIL_CU
        411s bash   export RUSTUP_HOME=/home/runner/.rustup CARGO_HOME=/home/runner/.cargo PYTHONPATH=$PWD/AIL_CURRENT PYTHONDONTW
        176s bash   export PYTHONPATH=$PWD/AIL_CURRENT PYTHONDONTWRITEBYTECODE=1; python3 -B -m unittest -v AIL_CURRENT.test_ail_s
         21s bash   export RUSTUP_HOME=/home/runner/.rustup CARGO_HOME=/home/runner/.cargo PYTHONPATH=$PWD/AIL_CURRENT; ulimit -v 
         13s bash   export RUSTUP_HOME=/home/runner/.rustup CARGO_HOME=/home/runner/.cargo PYTHONPATH=$PWD/AIL_CURRENT; python3 -B
         11s bash   ls -la /home/runner/.rustup 2>/dev/null; find /home/runner/.rustup -maxdepth 4 -type f -name cargo 2>/dev/null
         10s bash   mkdir -p /tmp/probes cat > /tmp/probes/wordbag_basic.py <<'EOF' from ail_ffi import *  link("/tmp/crate_wordba
          9s bash   export PYTHONPATH=$PWD/AIL_CURRENT PYTHONDONTWRITEBYTECODE=1 for p in wordbag_basic slugify_edges walk_callbac

## review 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
**What the change really does:** adds four Rust crate examples (`wordbag`, `slugify`, `walk`, `bits` with a vendored `tinydep`), extends the example test and the README measurements/limitations. No compiler, runtime, FFI or bindgen file is touched; the only non-example edits are the example test and the generated manifest hash.

**Probes** (my runner mirrors `cmp.sh`: CPython, `AIL_UNIFIED_FORCE=1`, default; artifacts copied in; `/tmp/rprobes/`)
- `w_big_nohandle.py` + `--exact-int`: u64 > 2**63 without a `Handle` → exact in CPython and both AIL builds, identical stdout. Confirms README limitation 4.
- `w_exact.py` + `--exact-int`: same value with a `Handle` → both AIL builds print `before 0` then stop with `OverflowError: integer overflow in +`. Allowed by the task ("or stop loudly"), and documented.
- `s_direct.py` (slugify): cap 0, cap == needed, cap == needed−1, empty input, high bytes, stale buffer reuse — identical stdout on both builds.
- `k_cb3.py` (walk): n = −3, n = 0, i32 wrapper sums, callback raising at step 3 — identical stdout on both builds; no callback output after the call returns.
- `plain.py`: `--debug-dir .../program.c` byte-identical HEAD vs `/tmp/base` (`2cb8be80…`). Trivially expected, since no compiler file changed.
- Direct runs of all four new `main.py` binaries vs `python3` through the `.so`: same stdout; sizes exactly the README's bytes (5,439,640 / 5,424,984 / 52,552 / 23,456); median times 1.9/1.3/1.0/1.0 ms vs 63.8/61.2/64.4/59.7 ms here (same order as the report).
- Named refusals (pre-existing subset, compiler untouched): `Handle` reaching a stub via a list item or dict value, and a callback reading a module-level list.

**Tests:** `test_ail_examples_crate` ok (13.8 s). `test_ail_safetynet` fails only `S4_generators_gc` under `ulimit -v 1500000` — and fails identically on `/tmp/base`; passes on HEAD without the cap (191 s). Pre-existing/environmental.

**Claims:** 4 crates + APIs verified; measurements verified (bytes exact, times consistent); "7 examples match CPython" verified; `wordbag_huge` stop verified; "38 passed, 1 skipped" not independently checked (only the two required modules run); safetynet-cap explanation verified. One soft miss: the "vendored dependency" is a 7-line crate the worker wrote, not a crate taken from the registry — it proves offline path-dependency builds but is a weak demonstration. Also one commit for four sub-steps, and the 20 shard checks are unverified (no push allowed in this runner).

**Pre-existing:** safetynet S4 under a 1.5 GB cap; `Handle`/callback-in-list subset refusals; u64 > 2**63 stops in the default build (limitations 1 and 4).

VERDICT: ACCEPT
[commandcode stop=end_turn turns=38 out_tokens=30515]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-06T05:27:07Z
