# job job-prog8-11021515  started 2026-11-02T06:26:04Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed both review defects and committed as `119e822`.

- Mixed `NSUM`/float returns: `ast.Return` now wraps definite float values with `ail_nsum_from_float` when `ctx.ret == NSUM`, clearing the int-0 flag. `p14c` and `/tmp/probes/mixed_return_all.py` match CPython on both builds and stay typed under `--strict`.
- Docs: `SEMANTICS.md` and the C1 `DIFFERENCES.md` row now describe `ail_nsum { double v; int64_t is_int0; }`, not the `-0.0` sentinel.
- Added `MIXED_RETURN` coverage to `test_ail_prog8`.
- Passing: `test_ail_prog8` (9), `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_nested_lists`, `test_ail_float_argument_widening`, `test_ail_spec_fixes`. `update_manifest.py --check` exits 0.
[cost $0.0000, opencode tokens {"total": 2373940, "input": 70043, "output": 10476, "reasoning": 4909, "cache.write": 0, "cache.read": 2288512}]
    tool time: bash 9.4 min, edit 0.0 min, read 0.0 min
        175s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 test_ail_corpus_findings3.py 2>&1 | tail -15; echo C
        154s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 test_ail_safetynet.py 2>&1 | tail -15; echo SAFETY_E
         88s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 test_ail_files.py 2>&1 | tail -15; echo FILES_EXIT $
         66s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 test_ail_spec_fixes.py 2>&1 | tail -15; echo SPEC_EX
         28s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 test_ail_nested_lists.py 2>&1 | tail -12; echo NESTE
          9s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check && echo MANIFEST_OK; cd AIL_CUR
          8s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 test_ail_prog8.py -v 2>&1 | tail -40
          6s bash   cat > /tmp/probes/mixed_dict.py <<'EOF' def make() -> dict[str, float]:     d: dict[str, float] = {}     d["v"

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review report

**What the change does:** In the typed code generator, a `return <float>` inside a function whose settled return kind is `NSUM` is now wrapped in `ail_nsum_from_float(...)` (flag cleared); docs (`SEMANTICS.md`, C1 `DIFFERENCES.md`) were updated from the old `-0.0` sentinel to the `ail_nsum { double v; int64_t is_int0; }` struct; `MIXED_RETURN` was added to `test_ail_prog8`.

### Probes (HEAD, both `cmp.sh` builds)
| probe | covers | result |
|---|---|---|
| `p6_exact` | exact old review defect: `if n>0: return sum(xs)` / `return 1.5` | base default: compile error (`double` vs `ail_nsum`); HEAD both builds match CPython |
| `p1_sources` | float via arg, list item, attribute, dict value, computed expr, local `s=sum(xs)`, empty/non-empty | both match (strict falls back on a pre-existing annotation issue, see below) |
| `p2_control` | `else`, loop, ternary, via-name, nested branches | both match |
| `p3_edge` | `-0.0`, `0.0`, `1e308`, `1e-320`, `sum([1e308,1e308])` overflow | both match; strict-typed |
| `p4_uses` | arithmetic, compare, bool, int/float conversion, `%`/format, dict/list storage | both match |
| `p8_kinds` | int / bool / compare on the other return path | both match (named refusal or general) |
| `p9_reverse` | reversed ternary, tuple unpack, `float(...)`, `sum(xs)*1.0` | both match |
| `p5_nofeature` | program using no NSUM feature | generated C byte-identical to base |
| 10 `lab/compare/src/*/main.ail` | no-feature C | all 10 `program.c` byte-identical to base |

### Tests
`test_ail_prog8` (9 tests) and `test_ail_safetynet` pass on HEAD (`par_check -j 2`). `update_manifest.py --check` exits 0.

### Report claims
- Mixed `NSUM`/float return fixed — **verified** (`p6_exact`, `p3_edge`; base fails, HEAD matches).
- Wrapping clears the int-0 flag — **verified** (`-0.0`/`0.0` stay `-0.0`/`0.0`, `p3_edge`).
- Docs now describe the struct — **verified** (grep/diff; only stale code comments remain at `pyfunc.py:8689,22883`).
- `MIXED_RETURN` added and typed — **verified** (test passes, asserts `ail_nsum_from_float`).
- `test_ail_prog8`(9), `test_ail_safetynet` — **verified**; `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_nested_lists`, `test_ail_float_argument_widening`, `test_ail_spec_fixes` — **unverified** (not run, per review scope).
- `update_manifest.py --check` 0 — **verified**.
- Worker's own `/tmp/probes/mixed_return_all.py`, `p14c` — **unverified** (not present); equivalent shapes covered above.

### Pre-existing / notes
- `from_local`-style / `via_name` strict refusals ("return annotation float disagrees with inferred int") are identical on base (`p1`, `p2`, `p9`) — pre-existing.
- Stale code comments still mention the `-0.0` sentinel (`pyfunc.py:8689`, `:22883`); docs and behaviour are consistent, so not blocking.
- No speed check: the new path only compiles programs that previously failed to build, and non-NSUM programs' C is unchanged.

### Unverified
- Wider suite, instruction counts, and the modules not listed under Tests (not run per review instructions).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1818022, "input": 112975, "output": 8707, "reasoning": 14676, "cache.write": 0, "cache.read": 1681664}]
    tool time: bash 4.9 min
        152s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_prog8 test_ail_s
         73s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/cch /tmp/cbase && mkdir -p /tmp/cch /tmp/cbase && for t in b
         17s bash   cd /tmp/base && for p in p1_sources p2_control p3_edge p4_uses p5_nofeature; do echo "===== base $p ====="; ba
         16s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p1_sources p2_control p3_edge p4_uses p5_nofeature; do echo "==
          9s bash   cd /home/runner/work/ail-ci/ail-ci && grep -rn -- "-0.0.*sentinel\|sentinel.*-0.0\|empty-sum sentinel\|empty s
          7s bash   cd /tmp/rprobes && cat > p9_reverse.py <<'EOF' def rev(xs: list[float], n: int) -> float:     if n > 0:       
          6s bash   cd /tmp/rprobes && cat > p7_annotlocal.py <<'EOF' def f(xs: list[float], n: int) -> float:     if n > 0:      
          3s bash   cd /tmp/rprobes && cat > p6_exact.py <<'EOF' def g(xs: list[float], n: int) -> float:     if n > 0:         re

## full suite
test_ail_builtin_api

## worker report (suite fix)
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed as `a34fadb`.

- Cause: `test_ail_builtin_api` compiles `let output: float = sum(v0)`. The `float` annotation seeded `output` as `FLT`, so the later `sum()` assignment was refused as a float-local NSUM write.
- Fix: `_seed_local_annotations` now seeds an annotated local as `NSUM` when its initializer is `NSUM`, keeping the local and C return type consistent and exact.
- Tests: `test_ail_builtin_api`, `test_ail_prog8`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_spec_fixes` all pass; manifest check passes.
[cost $0.0000, opencode tokens {"total": 2773406, "input": 338922, "output": 6411, "reasoning": 9257, "cache.write": 0, "cache.read": 2418816}]
    tool time: bash 5.9 min, edit 0.0 min
        290s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_builtin_api test_ail_prog8 test
         25s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest -q test_ail_builtin_api 2>&1 | tail -80
         25s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest -q test_ail_builtin_api 2>&1 | tail -30
          9s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest -q test_ail_prog8 2>&1 | tail -30
          1s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 - <<'PY' import sys sys.path[:0]=['.','python/pkg-v1
          1s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 - <<'PY' import sys sys.path[:0]=['.','python/pkg-v1
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git show --stat HEAD~1 && git log --oneline -6 --all | head -20

## full suite again
no new failures

FINAL VERDICT: ACCEPT  2026-11-02T09:33:25Z
