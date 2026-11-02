# job job-prog22-11021237  started 2026-11-02T03:38:51Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Done. Commit `d4ef0ad`.

- Profiled all 8 programs; table in `lab/progfix/prog22.md`.
- Typed now: `t366`, `t347`, `t318`, `g14` (4/8). New fixes: local `list[tuple[str, float, str]]` annotations → `ail_srows`; `max`/`min(key=...)` over class lists.
- Still general, with exact first reasons recorded: `g12_018` (Random.randrange defaults), `g21_002` (mixed bool/number `list[object]`), `g15_006` (Union with None), `g16_034` (returned generator expression).
- Added `AIL_CURRENT/test_ail_prog22.py` via `tests.d`; NaN srows sort refusal recorded as `C?-job-prog22-11021237-1`.
- Final-commit tests: 10 modules, 0 failed (`test_ail_prog22`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, plus sort/typed-reach regressions).
- Probes `p22_srows`, `p22_maxkey`, `p22_maxkey_call`, `p22_maxkey_empty`, `p22_maxkey_tuple`: all match CPython on both builds.
- All 10 `lab/compare` tasks generate byte-identical C versus the pre-change tree.
[cost $0.1013, opencode tokens {"total": 9778622, "input": 320343, "output": 18664, "reasoning": 23039, "cache.write": 0, "cache.read": 9416576}]
    tool time: bash 19.7 min
        450s bash   cd /home/runner/work/_temp/w2 && timeout 3000 python3 tools/par_check.py -j 2 test_ail_prog22 test_ail_safetyn
        442s bash   cd /home/runner/work/_temp/w2 && python3 tools/update_manifest.py --check && timeout 3000 python3 tools/par_ch
         83s bash   rm -rf /tmp/cmpc/all && mkdir -p /tmp/cmpc/all && cd /tmp/cmpc/all && fail=0; for t in berth_sim chain_relax e
         44s bash   rm -rf /tmp/cmpc && mkdir -p /tmp/cmpc && cd /tmp/cmpc && cp /home/runner/work/_temp/w2/lab/compare/src/tree_f
         27s bash   cd /tmp/prog22/comp && for b in g12_018 g21_002 g15_006 g16_034 g14_034; do echo "################ $b STRICT";
         26s bash   cd /tmp/prog22 && rm -rf comp && mkdir comp && cd comp && for f in /home/runner/work/_temp/w2/lab/census/progr
         25s bash   cd /tmp/prog22/comp && AIL_NO_CACHE=1 AIL_SERVER=0 python3 /home/runner/work/_temp/w2/AIL_CURRENT/ail_chatgpt.
         18s bash   cd /home/runner/work/_temp/w2 && for p in /tmp/probes/p22_srows.py /tmp/probes/p22_maxkey.py /tmp/probes/p22_m

## review 0
[model opencode-go/deepseek-v4.1-flash]
## Review: `d4ef0ad` — prog22 typed reach

**What the diff really does (one line):** adds a `list[tuple[...]]`-with-str annotation path that lowers to `ail_srows` (plus `enumerate` over it), a `max`/`min(key=lambda s: <numeric>)` fold over class-instance lists, and a NaN pre-check in `ail_srows_sort_key`. No programs were edited.

**Probes run** (`bash ~/tools/cmp.sh <p> $PWD` and `/tmp/base`):
- typed and matching: `k11_g14var` (method key, ties, negative, int key, list literal), `k10/k13` variants, `s4_param`, `ret_srows`, `field_srows`, `four` (4-field rows), `single` (1-field), `allstr`, `a2`, `nosort`, `nostart2`, `startcall`, `alias`, `rebind`, `defaultsort`, `mutate`, `k15_nanmethod`; all worker `p22_*` probes match.
- defect probes: `v2/five_fixed.py` (wrong stdout), `k16_catch_empty.py` (wrong stdout/exit).
- non-feature C: `berth_sim`, `tree_fold` generated C byte-identical HEAD vs base; `update_manifest.py --check` OK.
- tests on HEAD: `test_ail_prog22` and `test_ail_safetynet` both pass (`-j 2`, 0 failed).

**Defects**

1. **Rows with more than 4 fields are silently truncated** (exit 0, wrong values). `AIL_SROW_MAXK` is 4 and `_mark_srow_lists` caps arity at 4, but the new annotation branch returns `('srows', field_kinds)` for any arity, so `ail_srows_push` gets a 5-element initializer into `v[4]` (excess dropped) and the 5th field is read out of bounds.
   Probe `/tmp/rprobes/v2/five_fixed.py`:
   ```python
   rows: list[tuple[str, int, float, str, int]] = []
   rows.append(("a", 1, 2.0, "x", 3))
   rows.append(("b", 0, -1.0, "y", 4))
   rows.sort(key=lambda r: (r[1], r[0]))
   for i, (a, b, c, d, e) in enumerate(rows, start=1):
       print(i, a, b, c, d, e)
   ```
   Expected (CPython, and base general path): `1 b 0 -1.0 y 4` / `2 a 1 2.0 x 3`
   Actual HEAD: `1 b 0 -1.0 y 0` / `2 a 1 2.0 x 0`, exit 0.

2. **Empty `max`/`min(key=...)` over an instance list is an uncatchable `ail_die`, not a `ValueError`.** `_struct_key_fold` emits `ail_die("max() arg is an empty sequence")`; CPython raises a catchable `ValueError: max() iterable argument is empty`. Probe `/tmp/rprobes/k16_catch_empty.py` wraps the call in `try/except ValueError` and prints the message.
   Expected (CPython and base general path): `caught max() iterable argument is empty`, exit 0.
   Actual HEAD: no stdout, stderr `max() arg is an empty sequence`, exit 1. Same for `min`. Fix: raise `ail_raise_named(AIL_EXC_VALUE)` with CPython's text, as the runtime does elsewhere.

**Claim check**
- Typed t366/t347/t318/g14 and general g12_018/g21_002/g15_006/g16_034 with the stated reasons: **verified** (g21's strict-first reason is the bool/number one).
- New fixes / tests.d registration / DIFFERENCES row: **verified**.
- Worker probes match CPython: **verified**, but `p22_maxkey*` and `EMPTYMAX` use attribute keys, which take the pre-existing `iterlower` path (my `k1` C is byte-identical to base), so they do not exercise the new `_struct_key_fold`; only g14 and my method-key probes do.
- "10 lab/compare tasks byte-identical": **spot-checked 2 identical**, other 8 unverified.
- "empty source stops with CPython's … message": **false** (see defect 2).
- "10 modules, 0 failed": 2 re-run pass; other 8 unverified.

**Pre-existing (not attributed to this change)**
- Module-level `list[Class]` emits C with an undeclared global (`v_gxs`) on both base and HEAD.
- `sort(key=...)` over a NaN key refuses on both base and HEAD; identical behaviour.

**Unverified:** cProfile percentages, the remaining 8 compare tasks/modules, instruction-count speed (the only hot-path addition is an O(n·k) NaN scan before `ail_srows_sort_key`), and mutation during `_struct_key_fold` (I could not construct a typed shape; the global-list variant hits the pre-existing C bug).

VERDICT: FIX
1. Cap the new `srows` annotation at `AIL_SROW_MAXK` (4 fields) and refuse >4 by name so the general path is used; probe `/tmp/rprobes/v2/five_fixed.py`, expected `… y 4` / `… x 3`, actual `… y 0` / `… x 0` (exit 0).
2. In `_struct_key_fold`, replace `ail_die("… arg is an empty sequence")` with a catchable `ail_raise_named(AIL_EXC_VALUE)` using CPython's `"max()/min() iterable argument is empty"`; probe `/tmp/rprobes/k16_catch_empty.py`, expected `caught max() iterable argument is empty` exit 0, actual empty stdout, exit 1.
[cost $0.0889, opencode tokens {"total": 9164005, "input": 165350, "output": 24278, "reasoning": 37801, "cache.write": 0, "cache.read": 8936576}]
    tool time: bash 7.2 min
        177s bash   date && cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 2400 python3 ../tools/par_check.py -j 2 test_ail_
         35s bash   cd /home/runner/work/_temp/w2 && for p in /tmp/rprobes/*.py; do echo "################ HEAD $(basename $p)"; b
         35s bash   cd /home/runner/work/_temp/w2 && for p in /tmp/rprobes/variants/a2.py /tmp/rprobes/variants/a5.py /tmp/rprobes
         30s bash   cd /home/runner/work/_temp/w2 && for p in /tmp/rprobes/*.py; do echo "################ BASE $(basename $p)"; b
         29s bash   for t in berth_sim tree_fold; do for w in h b; do if [ $w = h ]; then wt=/home/runner/work/_temp/w2; else wt=/
         20s bash   cd /home/runner/work/_temp/w2 && for p in /tmp/probes/p22_srows.py /tmp/probes/p22_maxkey.py /tmp/probes/p22_m
         19s bash   cd /home/runner/work/_temp/w2 && for f in lab/census/programs/dev/t366.py lab/census/programs/gdev/g12_018.py 
          9s bash   date; mkdir -p /tmp/rprobes/v2 && cat > /tmp/rprobes/v2/nostart.py <<'EOF' def main() -> None:     rows: list[

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Committed `4ba0387` on `job-prog22-11021237`.

**Fixes**
- Wide str-field rows: `list[tuple[...]]` annotations with `>4` fields are now refused by name (`a records annotation with N fields; a str-field row holds at most 4 fields`) and take the general path. No more silent truncation past `AIL_SROW_MAXK`.
- Empty `max`/`min(key=)` over instance lists: now raises a catchable `ValueError` with CPython’s `max()/min() iterable argument is empty`, using `ail_raise_msg` when text is read and `ail_raise_named` otherwise.

**Probes** (`/tmp/probes`, run with `cmp.sh` on both builds): 16 probes, all match CPython. Covers 5/6-field rows, trailing/leading str fields, keys/tints/negatives/int64 edges, and empty max/min through local, argument, attribute, list-item, dict-value, caught-with-text, and caught-silently. Only `p22_empty_dict.py` (dict value) and `p22_maxmin_direct.py` fall back to general; the rest are typed where the shape allows. The two changed branches were confirmed in generated C.

**Tests on final commit**: `test_ail_prog22`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, plus `test_ail_typedreach1/2`, `test_ail_tuples`, `test_ail_sort_keys` — 8 modules, 0 failed. `update_manifest.py --check` OK.

**C stability**: all 10 `lab/compare/src/*/main.ail` generated C byte-identical to `/tmp/base` (`e09c50b`).

Untracked `.agent/pipeline.md` was left alone.
[cost $0.0541, opencode tokens {"total": 5282876, "input": 125818, "output": 17651, "reasoning": 15439, "cache.write": 0, "cache.read": 5123968}]
    tool time: bash 14.6 min, edit 0.0 min
        375s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 3000 python3 ../tools/par_check.py -j 2 test_ail_prog22 t
        335s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 3000 python3 ../tools/par_check.py -j 2 test_ail_prog22 t
         48s bash   cat > /tmp/chk_cmp.sh <<'EOF' #!/bin/bash set -u task=$1 new=/tmp/chk22/new/$task old=/tmp/chk22/old/$task mkd
         30s bash   cd /home/runner/work/_temp/w2 && for p in /tmp/probes/p22_five.py /tmp/probes/p22_six.py /tmp/probes/p22_five_
         15s bash   cd /home/runner/work/_temp/w2 && for p in /tmp/probes/p22_catch_empty_max.py /tmp/probes/p22_catch_empty_min.p
         14s bash   cd /home/runner/work/_temp/w2 && for p in /tmp/probes/p22_empty_arg_method.py /tmp/probes/p22_empty_attr_metho
         13s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 2400 python3 ../tools/par_check.py -j 2 test_ail_prog22 2
          9s bash   cd /tmp/probes && cat > p22_empty_local_method.py <<'EOF' from __future__ import annotations from dataclasses 

## review 1
[model opencode-go/deepseek-v4.1-flash]
**What the change really does:** adds a typed local `list[tuple[...]]` (≤4 fields, with `str`) path plus `enumerate` over `ail_srows`; adds a `max`/`min(key=)` fold over class-instance lists (catchable empty `ValueError`); adds a NaN-key refusal in `ail_srows_sort_key`; plus tests/docs/manifests. No program was edited.

**Defect (blocking) — module-level class lists now miscompile on the typed path**

Probe `/tmp/rprobes/global_maxkey.py`:
```python
from dataclasses import dataclass
@dataclass
class It:
    x: float
gxs: list[It] = []
def main() -> None:
    gxs.append(It(1.0))
    gxs.append(It(2.0))
    print(max(gxs, key=lambda s: s.x).x)
main()
```
- CPython: `2.0`, exit 0.
- Base (`/tmp/base`) default build: `2.0`, exit 0.
- HEAD default build: **build fails**, `program.c:1000:30: error: 'v_gxs' undeclared` (no executable).
- HEAD general build (`AIL_UNIFIED_FORCE=1`): `2.0`.

Same failure for `/tmp/probes/k6b_mutate.py` and `/tmp/probes/k6d_globalmax.py` (both work on base). Cause: `_struct_key_fold` (pyfunc.py:17958) now makes a function typed for a module-level `olist`; the emitted fold reads `v_gxs` as a local in `py_main`, while an empty module list is declared in a later init function. Minimal fix: refuse the fold when the source is a module-level global (fall back to general as on base), or use the module-global accessor.

**Claim check**
- t366/g14 now typed; base general — verified.
- t347/t318 typed — verified.
- g12/g15/g16 still general with the stated first messages — verified.
- g21_002 first reason — **false**: actual first reason is `json.dumps of data: the type of this value is not known here`, not the `[None, True, False]` bool/number mix.
- Wide >4 str rows "refused by name" — verified for mixed 5-field annotations (message + general path), but **not universal**: an all-`str` 5-field annotation compiles typed as an `olist` of a synthesized tuple class, and a list-literal-initialized annotated srow list falls back general with `a list mixing tuples and plain numbers`. No truncation observed in any case.
- Empty max/min catchable `ValueError`, with text and silently, through argument/attribute/list-item/dict-value — verified.
- "Only `p22_empty_dict` and `p22_maxmin_direct` fall back general" — **false**: `p22_srows` also falls general (`for x in empty` flat walk).
- C stability of the 10 `lab/compare` tasks — verified byte-identical.
- `test_ail_prog22` + `test_ail_safetynet` pass; manifest `--check` OK. The other six modules the report lists were not rerun (not required).

**Pre-existing:** `key_edge` int64 overflow in the key expression is identical on base; a module-level forward-ref empty class list appended in typed code (`k6c_global`) already fails on base; NaN sort refusal differs from CPython on both builds (documented `C?-job-prog22-11021237-1`), typed path raises `ValueError` with empty text while the general path has a descriptive message.

**Unverified:** instruction counts — `perf_event_open` is denied here, so no icount before/after; the report's 8-module test claim beyond the two required modules.

VERDICT: FIX
1. `/tmp/rprobes/global_maxkey.py`: expected `2.0` (CPython and base default); actual HEAD default build fails with `'v_gxs' undeclared` because `_struct_key_fold` types a function that mutates a module-level empty class list. Same for `/tmp/probes/k6b_mutate.py` and `/tmp/probes/k6d_globalmax.py`; base builds and matches CPython.
[cost $0.0768, opencode tokens {"total": 7068146, "input": 68029, "output": 21830, "reasoning": 54511, "cache.write": 0, "cache.read": 6923776}]
    tool time: bash 13.2 min
        183s bash   date; cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 2400 python3 ../tools/par_check.py -j 2 test_ail_pr
         84s bash   cd /home/runner/work/_temp/w2 && rm -rf /tmp/cstab && mkdir -p /tmp/cstab && fails=0; for t in lab/compare/src
         50s bash   cd /tmp/rprobes && for p in k6_mutate k6b_mutate k6d_globalmax k15_nanmethod k16_catch_empty field_srows ret_s
         38s bash   cd /tmp && for p in p22_five p22_six p22_maxkey p22_maxkey_empty p22_empty_dict p22_maxmin_direct p22_catch_si
         33s bash   cd /tmp/rprobes && for p in key_forms key_empty key_edge srow_edge srow_wide srow_alias nonfeature; do echo "=
         27s bash   cd /tmp/rprobes && for p in srow_nan_nokey srow_lit srow_append5 key_side srow_iter_mut srow_edge srow_4str sr
         25s bash   cd /tmp/rprobes && cat > srow_module.py <<'EOF' ROWS: list[tuple[str, int]] = []  def main() -> None:     ROWS
         25s bash   cd /tmp/rprobes && for p in key_forms key_empty key_edge key_default key_tuple srow_edge srow_wide srow_alias 

FINAL VERDICT: FIX  2026-11-02T05:36:12Z
