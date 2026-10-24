# job job-pre32-10240902  started 2026-10-24T00:02:56Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
​Fixed `r52_ovf` on `job-pre32-10240902` in commit `16461e7`.

- `ail_syntax.fold_constants` now evaluates constant expressions containing `**` exactly when the normal int64 fold rejects an intermediate. `2**63 - 1` and `-(2**63)` match CPython on both builds; genuinely out-of-range constants are refused by name (`int64 literal out of range`), with the minimum written as `(-9223372036854775807 - 1)` so the typed path never sees an out-of-range positive literal.
- Added `AIL_CURRENT/test_ail_pre32.py`, registered it in `ail_check.MODULES`, added the DEVLOG entry, and refreshed/checked `MANIFEST.json`.
- Probes: `p32_values`, `p32_arg`, `p32_list`, `p32_attr`, `p32_dict`, `p32_safe`, `p32_negative`, `r52a`, `r52c` — `g` and `d` both same stdout as CPython. `p32_refuse` — both builds refused by name. `r52e`/`ovf` also refused by name.
- Tests on the final commit: `test_ail_pre32`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` all passed (`-j 2`, 255s). Also passed earlier: `test_ail_modconst`, `test_ail_python_syntax`.

`f52_10` probes matched; `f52_t4` only showed an obscure module-level frozenset-key corner, so `r52_ovf` was the clear recorded difference. Variable-exponent powers (`2**e`, list-element operands) still stop at the int64 runtime limit; this fix targets the recorded constant expressions.
[cost $0.0000, opencode tokens {"total": 10694793, "input": 340278, "output": 23358, "reasoning": 46448, "cache.write": 0, "cache.read": 10284709}]
    tool time: bash 15.0 min, write 0.0 min
        342s bash   python3 tools/par_check.py -j 2 test_ail_pre32 test_ail_safetynet test_ail_files test_ail_corpus_findings3 tes
        257s bash   python3 tools/par_check.py -j 2 test_ail_pre32 test_ail_safetynet test_ail_files test_ail_corpus_findings3
         47s bash   cat > /tmp/probes/t4d.py <<'EOF' S = frozenset({(1, 2), (3, 4)})   def main() -> None:     print(len(S))     p
         40s bash   for p in /tmp/probes/p32_*.py /tmp/probes/r52a.py /tmp/probes/r52b.py /tmp/probes/r52c.py /tmp/probes/r52d.py 
         32s bash   for p in /tmp/probes/p32_*.py /tmp/probes/r52a.py /tmp/probes/r52c.py; do echo "=== $(basename "$p")"; bash ~/
         31s bash   cd /home/runner/work/ail-ci/ail-ci; for p in /tmp/probes/*.py; do echo "===== $p"; timeout 900 bash ~/tools/cm
         18s bash   cat > /tmp/probes/r52a.py <<'EOF' def main() -> None:     print(2**63 - 1)     print(-(2**63))     print((-2)*
         18s bash   cat > /tmp/probes/t4i.py <<'EOF' S = frozenset({(1, 2), (3, 4)}) D = {S: "value"}   def main() -> None:     sa

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: `job-pre32-10240902` (commit `16461e7`)

Base worktree: `/tmp/base` at `56e716b`. HEAD: `16461e7`. Probes in `/tmp/rprobes/`.

### Probes run (`bash ~/tools/cmp.sh … $PWD`, both `g` and `d`)

| probe | CPython | HEAD | base |
|---|---|---|---|
| `core` (boundary arithmetic: `2**63-1`, `-(2**63)`, `(-2)**63`, `3**39`, `//`, `%`, `~`, `* -1`) | ok | both same | runtime `integer overflow` |
| `channels` (arg/default/list/tuple/attr/dict) | ok | both same | runtime overflow |
| `minctx`, `fstr`, `multi`, `overlap3` | ok | both same | — |
| `refuse` (`2**63`) | ok | both refuse `int64 literal out of range` | runtime overflow |
| `dead` (`if False: print(2**63)`) | ok | both refuse by name (acceptable) | ok |
| `overlap10` | `-1` | **both print `-172036854775808`** | runtime overflow |
| `overlap6`, `overlap1`, `overlap4`, `overlap2`, `overlap5` | ok | **both fail to compile: `unmatched ')'`** | runtime overflow |

`program.c` is byte-identical HEAD vs base for `g00_000` (no feature) and `g03_026` (non-constant `lam**k`); only debug-report paths differ, so no hot-code change (icount not needed).

### Defect 1 (blocking): overlapping source edits corrupt/wrong the module

`_fold_powers` records an edit for a constant `**` subexpression, then the module-level loop records an **overlapping ancestor** edit when the whole value folds via a known name (`known`), or when the whole value is a non-int (`str`/`float`) whose child was edited. Edits are applied with stale byte offsets after the inner replacement, cutting/duplicating text.

- Silent wrong value:
```python
A = 9223372036854775807
B = A - 2**63

def main() -> None:
    print(B)

main()
```
  expected `-1`; actual (both builds) `-172036854775808`.
- Compile error (not a named refusal):
```python
A = "x" * (2**63 - 2**63)

def main() -> None:
    print(repr(A))

main()
```
  expected `''`; actual (both builds) `p.ail:4:2: unmatched ')'`. Same for `A = 2**3; B = A - (2**63 - 1)` (expected `-9223372036854775799`) and `A = (2**63) / 2`.

Fix direction: if an ancestor is edited, suppress descendant edits (and vice-versa); module edits must be checked for range overlap. The added `test_ail_pre32.py` only uses direct expressions, so it does not catch this.

### Claims
- Direct `2**63 - 1`, `-(2**63)` now match CPython in both builds — **verified**.
- Out-of-range constant refused by name — **verified** (`refuse`).
- "exact only when the normal fold rejects an intermediate" — **false**: the module loop now passes `exact=True` unconditionally (this is what enables the float/str overlaps).
- Added test/registration/DEVLOG/MANIFEST — **verified** (`update_manifest.py --check` exit 0).
- `f52_t4` recorded variable-bound frozenset case — **verified fixed** on HEAD (`t4a,b,d,f,i,j,m,n` match). `t4h` (module-level dict keyed by frozenset of string tuples) still `KeyError`, but identically on base.
- `test_ail_pre32`, `test_ail_safetynet`, `test_ail_check` pass on HEAD (123 s, `-j 2`). `test_ail_files`/`test_ail_corpus_findings3` not rerun (review scope).

### Pre-existing
- `t4h`: module-level `{frozenset({(1,"a"),(2,"b")}): ...}` → `KeyError`; same on base, not caused by this change.

### Unverified
- `test_ail_files`, `test_ail_corpus_findings3` (not rerun by design).
- icount before/after: skipped because generated C is identical on the sampled programs.

VERDICT: FIX
1. Overlapping source edits in `fold_constants` corrupt module-level expressions that mix a known module constant (or a str/float result) with a foldable `**` subexpression. Probes: `A = 9223372036854775807; B = A - 2**63` → expected `-1`, actual `-172036854775808` (both builds); `A = "x" * (2**63 - 2**63)` → expected `''`, actual compile error `p.ail:4:2: unmatched ')'` (both builds). Suppress the inner edit when an ancestor is rewritten (or merge the edits) and add a regression test for module-level assignments.
[cost $0.0000, opencode tokens {"total": 1369546, "input": 84540, "output": 20627, "reasoning": 16251, "cache.write": 0, "cache.read": 1248128}]
    tool time: bash 5.2 min
        125s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1200 python3 ../tools/par_check.py -j 2 test
         32s bash   cd /home/runner/work/ail-ci/ail-ci && for p in core channels refuse dead shadow; do echo "########## $p HEAD";
         28s bash   cd /home/runner/work/ail-ci/ail-ci && for p in t4a t4b t4d t4f t4i; do echo "########## $p HEAD"; timeout 300 
         23s bash   cd /home/runner/work/ail-ci/ail-ci && for p in t4h t4j t4m t4n; do echo "########## $p HEAD"; timeout 300 bash
         18s bash   cd /tmp/rprobes && cat > overlap6.py <<'EOF' A = "x" * (2**63 - 2**63)   def main() -> None:     print(repr(A)
         14s bash   cd /tmp/base && for p in t4h t4n; do echo "########## $p BASE"; timeout 300 bash ~/tools/cmp.sh /tmp/probes/$p
         13s bash   cd /tmp/rprobes && cat > overlap10.py <<'EOF' A = 9223372036854775807 B = A - 2**63   def main() -> None:     
         12s bash   cd /tmp/rprobes && cat > multi.py <<'EOF' A = (2**63      - 1)   def main() -> None:     print(A)     print((2

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed the overlapping-edit corruption in `fold_constants`: only the outermost edit of an overlapping source range is now applied (`AIL_CURRENT/ail_syntax.py`). Added module-level overlap and ancestor-overflow regressions to `test_ail_pre32.py`.

Commit: `431eae4` (manifest check exit 0).

Probes (`bash ~/tools/cmp.sh … $PWD`, both `g` and `d`):
- `ov_known_sub`, `ov_str_mult`, `ov_known_minus`, `ov_float_div`, `ov_known_add`, `ov_nested`, `ov_bytes`, `ov_multi_assign`, `ov_no_pow`, `ov_boundary` — both builds same as CPython.
- `ov_ancestor_overflow` — both builds refuse by name (`int64 literal out of range`).
- Previously added `p32_*`, `f10*`, and constant-value probes remain matching; variable-exponent probes (`r52b`, `r52d`) still hit the documented runtime overflow and were not touched.

Tests on final commit (`-j 2`): `test_ail_pre32`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_check` — 5/5 passed, 254 s. No new DIFFERENCES row; this fixes an existing defect. Nothing pushed.
[cost $0.0000, opencode tokens {"total": 620718, "input": 34325, "output": 5012, "reasoning": 8069, "cache.write": 0, "cache.read": 573312}]
    tool time: bash 8.7 min
        256s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 3000 python3 ../tools/par_check.py -j 2 test_ail_pre
        125s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_pre
         82s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p32_values p32_negative p32_arg p32_attr p32_dict p32_list p32_
         35s bash   cd /home/runner/work/ail-ci/ail-ci && for p in ov_known_sub ov_str_mult ov_known_minus ov_float_div ov_known_a
         16s bash   cd /home/runner/work/ail-ci/ail-ci && for p in ov_known_sub ov_str_mult ov_known_minus ov_float_div ov_known_a
          7s bash   cd /home/runner/work/ail-ci/ail-ci && for p in r52b r52d; do echo "########## $p"; timeout 300 bash ~/tools/cm
          3s bash   cd /tmp/probes && cat > ov_multi_assign.py <<'EOF' A = 9223372036854775807 B = A - 2**63 C = A + (2**63 - 2**6
          0s bash   python3 - <<'PY' from pathlib import Path p = Path('/home/runner/work/ail-ci/ail-ci/DEVLOG.md') s = p.read_tex

## review 1
[model opencode/deepseek-v4.1-flash-free]
## Review: `job-pre32-10240902` (HEAD `431eae4`, base `work` @ `56e716b`)

Base worktree `/tmp/base`; probes in `/tmp/rprobes`. `date` start 00:55, end 01:13.

### Probes (`bash ~/tools/cmp.sh … $PWD`, both `g` and `d`)
- `rv_bound`, `rv_names`, `rv_multiline`, `rv_same_line`, `rv_stmt`, `rv_plain`, `rv_channels2`, `rv_default`, `rv_mod`, `rv_lambda`, `rv_combo`, `rv_overlap_deep`, `rv_powcancel`, `rv_powcancel2`, `rv_shiftmod`, `rv_min3`: same stdout as CPython in both builds.
- Prior failing overlaps `overlap1,3,4,5,6,7,8,9,10`: now same in both builds. `overlap2/11`: named refusal `int64 literal out of range` (acceptable).
- Worker `ov_*`: all same both builds; `ov_ancestor_overflow` refuses by name.
- `rv_float_func` (`(2**63)/2` in a function), `rv_ctx` (`2**63 - MAX`), `rv_big` (`10**50`): named compile refusal (acceptable).
- `r52b`, `r52d`: runtime `integer overflow` identically on HEAD and base (untouched, pre-existing).
- `f52_t4` (`t4a,d,i,n`) and `f52_10` (`f10a,d,h`): same as CPython on base and HEAD, so `r52_ovf` was the first still-differing recorded case.

### Tests on HEAD (`-j 2`)
`test_ail_pre32` 17.7 s, `test_ail_safetynet` 122.8 s, `test_ail_files` 131.5 s, `test_ail_corpus_findings3` 207.6 s, `test_ail_check` 0.2 s — all pass.

### Non-feature code
`program.c` byte-identical HEAD vs base for `g00_000`, `g25_020` (default and general), `g03_030`, `g03_026` (default). icount skipped: generated C is identical.

### Claims
- Outermost-only overlap fix: **verified**.
- Module-level overlap and ancestor-overflow regressions added: **verified**.
- `2**63 - 1` / `-(2**63)` fixed in both builds: **verified**.
- Genuine out-of-range constants refused by name: **verified**.
- Variable-exponent behavior unchanged: **verified**.
- `update_manifest.py --check` exit 0; commit `431eae4` present; branch not pushed: **verified**.

### Pre-existing (not blocking)
- `(1 << 63) - 1` and `2**65 - 2**65` inside function bodies still runtime-overflow; same constructs on base (`rv_bound`, `rv_shift65`).
- Function-body expression using a module constant as exponent (`E=63; print(2**E - 1)`) runtime-overflows; base fails likewise (`rv_expname`).
- Direct literal `-9223372036854775808` refused; base same (`rv_min2`).
- `t4h` module dict keyed by a frozenset of string tuples: `KeyError`; base same.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 2332982, "input": 147640, "output": 9040, "reasoning": 35246, "cache.write": 0, "cache.read": 2141056}]
    tool time: bash 10.9 min
        210s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1800 python3 ../tools/par_check.py -j 2 test
        125s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1200 python3 ../tools/par_check.py -j 2 test
         73s bash   for wt in /tmp/base /home/runner/work/ail-ci/ail-ci; do echo "########## WT $wt"; for p in t4a t4d t4i t4n f10
         38s bash   cd /home/runner/work/ail-ci/ail-ci && for p in ov_known_sub ov_str_mult ov_known_minus ov_float_div ov_known_a
         38s bash   cd /home/runner/work/ail-ci/ail-ci && for p in rv_bound rv_names rv_channels rv_default rv_float_func rv_shift
         25s bash   cd /tmp && for g in g00_000 g25_020 g03_030 g03_026; do for m in HEAD BASE; do wt=/home/runner/work/ail-ci/ail
         19s bash   for p in overlap1 overlap2 overlap3 overlap4 overlap5 overlap6 overlap10; do echo "########## $p HEAD"; timeou
         15s bash   cd /home/runner/work/ail-ci/ail-ci && for p in r52b r52d; do echo "===== $p HEAD"; timeout 300 bash ~/tools/cm

FINAL VERDICT: ACCEPT  2026-10-24T01:13:37Z
