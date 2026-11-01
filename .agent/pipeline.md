# job job-tup1-11020552  started 2026-11-01T20:52:43Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed both remaining review defects and committed as `6e0140c`.

**Changes**
- `tuplib.py`: a parameter with a default is never given a call-site inferred type, so `str`/`None`/`int`/`float`/`bool`/tuple defaults are not read as tuple classes.
- `tuplib.py` + `tupstmt.py`: `return None` and bare `return` now count as return types, so mixed tuple/`None` functions stay on the general path.
- Added 7 regression tests to `test_ail_tuple_reach` (28 total), updated `TUPLE_REACH.md`, and added a DEVLOG entry.

**Probes (20, all match CPython on default and forced-general builds)**
- `c1`, `c2`, `c4`, `c6`: `None` / bare return, before and after the tuple path, keyword-only.
- `c3`, `c5`, `c7`: mixed shape, method with `None` call site, default rebound in body.
- `d1`-`d5`: `str`/`None`/`int`/tuple defaults, same and different shapes.
- `e1`-`e8`: annotated tuple return with default, positional-only default, list-of-tuple default, default mentioning another parameter, `float`/`bool` defaults.

**Tests:** 6 modules, 0 failed (`test_ail_tuple_reach`, `test_ail_tuples`, `test_ail_typed_tuples`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`).

**C identity:** all 17 successful `lab/compare` builds are byte-identical to HEAD; the 3 failing `.py` builds fail identically. `update_manifest.py --check` is clean.
[cost $0.0000, opencode tokens {"total": 3145973, "input": 144276, "output": 10758, "reasoning": 12763, "cache.write": 0, "cache.read": 2978176}]
    tool time: bash 29.0 min, edit 0.0 min
        850s bash   cd lab/compare/src && rm -rf /tmp/lc_cmp && mkdir -p /tmp/lc_cmp && : > /tmp/lc_cmp/results.txt for task in *;
        393s bash   python3 tools/par_check.py -j 2 test_ail_tuple_reach test_ail_tuples test_ail_typed_tuples test_ail_safetynet 
        328s bash   python3 tools/update_manifest.py --check && python3 tools/par_check.py -j 2 test_ail_tuple_reach test_ail_tupl
         46s bash   cd /tmp/probes && for p in *.py; do echo "=== $p"; bash ~/tools/cmp.sh /tmp/probes/$p /home/runner/work/ail-ci
         44s bash   cd /tmp/probes && for p in *.py; do out=$(bash ~/tools/cmp.sh /tmp/probes/$p /home/runner/work/ail-ci/ail-ci 2
         26s bash   cd /tmp/probes && for p in *.py; do echo "=== $p"; bash ~/tools/cmp.sh /tmp/probes/$p /home/runner/work/ail-ci
         18s bash   cd /tmp/probes && cat > e1_ret_ann_default_tuple.py <<'EOF' def g(t=(0, "z")) -> tuple[int, str]:     return t
         12s bash   cd lab/compare/src/chain_relax && rm -rf /tmp/lc_out/b /tmp/lc_out/h && AIL_NO_CACHE=1 python3 /tmp/lc_base/AI

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review 2

**What the change really does:** `tuplib.py` stops recording call-site types for any parameter that has a default, and `tupstmt.py`/`tuplib.py` make `return None`/bare `return` contribute a `'none'` return type so mixed tuple/`None` functions are marked `mixed_ret`. The report omits one detail: the settled-return test changed from `len({code(t)}) == 1` to structural `all(t == seen[0])`; this is required because `code('none')` refuses, and is equivalent for the concrete types here.

**Probes (~40, /tmp/rprobes, both builds):** all match CPython on HEAD. The two review defects now pass: `r01`/`r02` (str/None default) and `r03`/`r04`/`r11` (None/bare return) match on HEAD and fail identically on base (`/tmp/base`), i.e. fixed. Boundary probes `r05`–`r15`, `s01`–`s15`, `t01`–`t10`, `u01`–`u03` cover int/float/bool/list/tuple defaults, positional-only and kw-only defaults, methods/`__init__`, list/dict/attribute values, nested functions, conditional returns, annotated returns, and default rebound in the body. Worker's `c1`–`c7`, `d1`–`d5`, `e1`–`e8` re-run: 20/20 match both builds.

**Pre-existing (identical on base, not blocking):** `s05` annotated `-> tuple[int,str]` with a `return None` path still crashes (rc 1) on both; `s15` `return t if flag else None` still crashes on both. Neither is caused by this change.

**Claims:**
- Defaults never inferred: verified (`r01`–`r09`, `s04`, `s08`, `t03`, `t08`, `u01`, `u02`).
- `None`/bare return count as return types: verified (`r03`, `r04`, `r11`, `r12`, `r15`, `s06`, `s11`, `t05`–`t07`, `u03`).
- 7 regression tests, 28 total: verified.
- Tests 6 modules, 0 failed: verified (ran all six with `-j 2`).
- `update_manifest.py --check`: verified clean.
- C identity: verified stronger — all 10 `lab/compare` `main.ail` builds have byte-identical `program.c`; `native_report.json` differs only in temp paths.
- Speed: not relevant (compile-time-only change; generated C identical).

No defect introduced; both review defects are fixed.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 656697, "input": 20740, "output": 5990, "reasoning": 8655, "cache.write": 0, "cache.read": 621312}]
    tool time: bash 11.0 min
        269s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 700 python3 ../tools/par_check.py -j 2 test_ai
         91s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 700 python3 ../tools/par_check.py -j 2 test_ail_tupl
         63s bash   cd /home/runner/work/ail-ci/ail-ci/lab/compare/src && rm -rf /tmp/cid2 && mkdir -p /tmp/cid2 && for task in be
         60s bash   cd /tmp/rprobes && for p in r*.py; do echo "=== $p"; bash ~/tools/cmp.sh /tmp/rprobes/$p /tmp/base 2>&1 | grep
         44s bash   cd /tmp/probes && for p in c*.py d*.py e*.py; do out=$(bash ~/tools/cmp.sh /tmp/probes/$p /home/runner/work/ai
         36s bash   cd /tmp/rprobes && cat > s01_list_value.py <<'EOF' def g(t, flag):     if flag:         return t     return No
         32s bash   cd /tmp/rprobes && for p in r*.py; do echo "=== $p"; bash ~/tools/cmp.sh /tmp/rprobes/$p /home/runner/work/ail
         22s bash   cd /tmp/rprobes && cat > t01_ann_default.py <<'EOF' def g(t="x") -> tuple[int, str]:     return t  def main():

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-01T22:56:24Z
