# job job-std_operator-11011752  started 2026-11-01T08:54:59Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Done. Commit `5fbcc11` on `job-std_operator-11011752` (not pushed).

**Result:** 12 programs in `lab/stdlib/operator/`; initial 3/12 built, final **11/12** build and match CPython stdout + exit code on default, general, and AIL_IR=0/1 builds. `sequence_concat.py` remains refused by name (follow-up in `RESULTS.md`).

**Fixes in `ail_syntax.py`:** `itemgetter(k,...)`, `attrgetter`, `methodcaller`, `setitem`/`delitem`, `contains`, `countOf`/`indexOf`, `truth`, `is_`/`is_not`. Zero-argument `itemgetter`/`attrgetter` now refuse naming the function instead of the misleading “operator read before assigned”.

**Probes** (`/tmp/probes`, both builds via `cmp.sh`):
- `p_itemgetter`, `p_itemgetter_mixed`, `p_attrgetter`, `p_methodcaller`, `p_mutate`, `p_contains_count_index`, `p_truth_is`, `p_through_values` — stdout/exit match CPython on both builds.
- `p_zero_itemgetter`, `p_zero_attrgetter` — refused by name; CPython raises TypeError.

**Tests run:** `test_ail_std_operator` OK (2), `test_ail_safetynet` OK (5), `test_ail_files` OK (18, 1 skipped), `test_ail_corpus_findings3` OK (2). Manifest updated; `update_manifest.py --check` passes.

**Generated C:** all 15 buildable `lab/compare` variants (10 `main.ail` + 5 `main.py`) byte-identical old vs new; the other 5 `main.py` variants build in neither version.
[cost $0.0253, opencode tokens {"total": 1677315, "input": 54214, "output": 9517, "reasoning": 11152, "cache.write": 0, "cache.read": 1602432}]
    tool time: bash 18.8 min, edit 0.0 min
        418s bash   cd /home/runner/work/_temp/w2 && rm -rf /tmp/cmpdbg/all && mkdir -p /tmp/cmpdbg/all && fail=0; same=0; skipped
        246s bash   cd /home/runner/work/_temp/w2 && timeout 3000 python3 -m unittest AIL_CURRENT.test_ail_corpus_findings3 2>&1 |
        170s bash   cd /home/runner/work/_temp/w2 && timeout 3000 python3 -m unittest AIL_CURRENT.test_ail_safetynet 2>&1 | tail -
         95s bash   cd /home/runner/work/_temp/w2 && timeout 3000 python3 -m unittest AIL_CURRENT.test_ail_files 2>&1 | tail -25
         49s bash   cd /home/runner/work/_temp/w2 && for p in /tmp/probes/p_attrgetter.py /tmp/probes/p_itemgetter.py /tmp/probes/
         39s bash   cd /home/runner/work/_temp/w2 && for p in /tmp/probes/p_*.py; do echo "##### $(basename $p)"; bash ~/tools/cmp
         34s bash   cd /home/runner/work/_temp/w2 && timeout 1800 python3 -m unittest AIL_CURRENT.test_ail_std_operator -v 2>&1 | 
         20s bash   cd /home/runner/work/_temp/w2 && bash ~/tools/cmp.sh /tmp/probes/p_itemgetter_mixed.py "$PWD" 2>&1; bash ~/too

## review 0
[model opencode-go/deepseek-v4.1-flash]
## Review: `stdlib operator` coverage

**What the change really does:** adds Python-surface lowerings in `AIL_CURRENT/ail_syntax.py` for multi-arg `itemgetter`, `attrgetter`, `methodcaller`, `setitem`/`delitem` (prelude helpers) and `contains`/`countOf`/`indexOf`/`truth`/`is_`/`is_not`, plus 12 lab programs, a test module and manifest/DEVLOG/DIFFERENCES rows. Matches the report.

**Probes** (`/tmp/rprobes`, both builds via `cmp.sh`):
- Match CPython: `p_attr_dotted`, `p_mutation_targets`, `p_scan_values2`, `p_truth_custom`, `p_errors`.
- Refused by name (acceptable): `p_zero`, `p_methodcaller_kw` (CPython itself TypeError), `p_starred_itemgetter`, `p_loop_capture`.
- **Wrong output (new): `p_loop_methodcaller`, `p_capture_methodcaller`, `p_loop_itemgetter`, `p_capture_itemgetter`.**

**Defects**
1. `methodcaller(...)` bound arguments are evaluated at *call* time, not at construction (`ail_syntax.py:2627`). Probe `/tmp/rprobes/p_loop_methodcaller.py`:
   ```
   checkers = []
   for s in [".txt", ".md"]:
       checkers.append(methodcaller("endswith", s))
   print([f("notes.txt") for f in checkers])
   ```
   CPython `[True, False]`; AIL `[False, False]` (default and general). Same with rebinding in `p_capture_methodcaller.py`: CPython `bAnAnA` / `['a', 'b;c']` / `.....x`, actual `baNaNa` / `['a,b', 'c']` / `..x`. Base refused `methodcaller`, so this is new.
2. Multi-argument `itemgetter` keys are likewise evaluated at call time (`ail_syntax.py:2595`), so all callables share the last loop value. Probe `/tmp/rprobes/p_loop_itemgetter.py`: CPython `[('a', 'b'), ('c', 'b')]`; AIL `[('c', 'b'), ('c', 'b')]`. (`p_capture_itemgetter` also shows it.) Single-arg `itemgetter` has the same flaw but already on base, so that part is pre-existing.

**Claims:** initial 3/12 builds and the per-program refusal messages verified; final 11/12 matches verified by `test_ail_std_operator` + probes; all 10 `lab/compare` `main.ail` and the 5 buildable `main.py` `program.c` byte-identical to base (other 5 unbuildable in both) verified; `test_ail_std_operator` OK (2) and `test_ail_safetynet` OK (5) verified; manifest `--check` passes; zero-arg refusal verified.

**Pre-existing:** single-arg `itemgetter(k)` late binding (`p_loop_itemgetter_single`: HEAD and base both `['c', 'c']` vs CPython `['a', 'c']`).

**Unverified:** worker's `test_ail_files`/`test_ail_corpus_findings3` runs (not re-run per instructions). Speed not checked: the change touches no hot runtime path.

VERDICT: FIX

1. `methodcaller` bound arguments are captured late: `/tmp/rprobes/p_loop_methodcaller.py` expected `[True, False]`, actual `[False, False]`.
2. Multi-arg `itemgetter` keys are captured late: `/tmp/rprobes/p_loop_itemgetter.py` expected `[('a', 'b'), ('c', 'b')]`, actual `[('c', 'b'), ('c', 'b')]`.
[cost $0.0242, opencode tokens {"total": 1313365, "input": 26335, "output": 7564, "reasoning": 19818, "cache.write": 0, "cache.read": 1259648}]
    tool time: bash 9.3 min
        287s bash   cd /home/runner/work/_temp/w2 && date && rm -rf /tmp/pdh /tmp/pdb && mkdir -p /tmp/pdh /tmp/pdb && cat /tmp/ta
        161s bash   cd /home/runner/work/_temp/w2 && date && timeout 1800 python3 tools/par_check.py -j 2 test_ail_std_operator te
         32s bash   cd /home/runner/work/_temp/w2 && date && rm -rf /tmp/idh /tmp/idb && mkdir -p /tmp/idh /tmp/idb && ls lab/comp
         27s bash   cd /home/runner/work/_temp/w2 && rm -rf /tmp/dh /tmp/db && mkdir -p /tmp/dh /tmp/db && for t in ticket_audit t
         21s bash   cd /home/runner/work/_temp/w2 && date && for p in /tmp/rprobes/p_*.py; do echo "##### $(basename $p)"; bash ~/
          7s bash   cd /home/runner/work/_temp/w2 && date && ls lab/stdlib/operator/*.py | xargs -P 2 -I{} bash -c 'f={}; n=$(base
          6s bash   cd /home/runner/work/_temp/w2 && date && for p in /tmp/rprobes/p_loop_capture.py /tmp/rprobes/p_starred_itemge
          4s bash   cd /tmp/rprobes && cat > p_loop_methodcaller.py <<'EOF' from operator import methodcaller suffixes = [".txt", 

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
(no final text)
[cost $0.0472, opencode tokens {"total": 4189602, "input": 93382, "output": 15890, "reasoning": 19146, "cache.write": 0, "cache.read": 4061184}]
    tool time: bash 41.9 min
        508s bash   rm -rf /tmp/ccmp/run && for task in berth_sim chain_relax echo_pack ledger_bin rail_transfer scar_life tally_l
        501s bash   date && timeout 3000 python3 tools/par_check.py -j 2 test_ail_std_operator test_ail_stdlib_batch1 test_ail_saf
        340s bash   python3 tools/update_manifest.py && python3 tools/update_manifest.py --check && date && timeout 3000 python3 t
        335s bash   sed -i 's|comp=$cur; else comp=$base;|comp=$cur/AIL_CURRENT; else comp=$base;|' /tmp/ccmp/one.sh rm -rf /tmp/c
        296s bash   date && timeout 3000 python3 tools/par_check.py -j 2 test_ail_std_operator test_ail_stdlib_batch1 test_ail_saf
        166s bash   rm -rf /tmp/base_cmp /tmp/ccmp && mkdir -p /tmp/base_cmp /tmp/ccmp && git archive ab13923 AIL_CURRENT | tar -x
        141s bash   for p in /tmp/rprobes/p_*.py /tmp/probes2/*.py /tmp/probes4/*.py /tmp/probes5/*.py /tmp/probes6/*.py; do n=$(b
         58s bash   for p in /tmp/rprobes/p_*.py; do echo "##### $(basename $p)"; bash ~/tools/cmp.sh $p "$PWD" 2>&1 | grep -E "cp
(cut off after 60 minutes)

## review 1
[model opencode-go/deepseek-v4.1-flash]
## Review: stdlib `operator` coverage

**What the diff really does.** `ail_syntax.py` adds Python-surface lowerings for `operator.itemgetter(k,...)`, `attrgetter`, `methodcaller`, `setitem`/`delitem`, `contains`, `countOf`/`indexOf`, `truth`, `is_`/`is_not`, plus two nested-lambda capture forms; adds 12 lab programs, RESULTS.md, a test module and manifests. It does not edit programs or benchmarks.

**Probes run** (`bash ~/tools/cmp.sh`, HEAD and /tmp/base where relevant):
- p1_scan: contains/countOf/indexOf on str/list/tuple/dict/set/empty, ValueError text — same on both builds.
- p2_item, p10_item2: multi-key/negative/dict/slice itemgetter, stored vs inline — p10 same (both exit 1 identically); p2 blocked by unrelated static typing.
- p3_attr_meth, p11_mc2: attrgetter dotted/multi, methodcaller kwargs/sort/nesting — p11 same.
- p4_setdel, p9_setdel2: setitem/delitem dict/list, slice, negative, OOB errors — same.
- p5_truth_is: truth on falsy/custom values same except string identity (pre-existing, see below).
- p6_noop: non-operator program same.
- p13_key_single: `key=itemgetter(idx())` calls idx 3× vs CPython 1× — **identical on base** (pre-existing).
- p14_key_multi: `key=itemgetter(idx(), 1)` — HEAD builds then `TypeError: '<' not supported between str and int`; CPython prints sorted rows, calls=1. Base refuses.
- p15_mc_filter: `filter(methodcaller("endswith", suffix()), names)` — HEAD prints all 3 names, calls=3; CPython `['a.md','c.md']`, calls=1. Base refuses.
- p16b_inline_rebind: `m=map(itemgetter(i),rows); i=1; list(m)` and `f=filter(methodcaller("endswith",s),...); s=".txt"; list(f)` — HEAD `[10,20,30]` / `['b.txt']`; CPython `['a','b','c']` / `['a.md','c.md']`. Base refuses.
- p17_is_plain: plain `is` on string literals — HEAD and base both differ from CPython (`False` vs `True`); pre-existing.
- p18_custom: `countOf`/`indexOf` on a class with only `__getitem__` — HEAD raises `TypeError: 'Seq' object is not iterable`; CPython counts/indexes it. Base refuses.
- p19/p20_empty: `itemgetter()`/`attrgetter()` refused by name (acceptable).
- Generated C via `--debug-dir`: all 10 `lab/compare/src/*/main.ail` `program.c` byte-identical to base; the 5 `main.py` variants that build also identical (other 5 don't build on either).

**Claims.**
- 12 lab programs, 11 build, `sequence_concat` refused by name, CPython match: verified by `test_ail_std_operator` + safetynet passing (initial 3/12 not re-run: unverified).
- Added lowering list: verified.
- “Arguments are evaluated once at construction”: **false** for the inline `key=`/`map()`/`filter()` path (defects 1–2).
- Generated C of lab/compare tasks byte-identical: verified for the cases above.
- Manifest/DEVLOG/DIFFERENCES rules: `update_manifest.py --check` passes; placeholder id and top DEVLOG entry present.

**Tests.** `test_ail_std_operator` ok (235 s), `test_ail_safetynet` ok (301 s).

**Pre-existing (do not block).** p13 single-key `key=itemgetter(expr)` re-evaluation; `is`/`operator.is_` on equal strings differs from CPython interning (plain `is` probe identical on base).

**Unverified.** Initial 3/12 count; `test_ail_files`/`test_ail_corpus_findings3` (reviewer scope excludes them); instruction counts (surface-only change; non-operator C is byte-identical).

**Defects**
1. Inline `key=` path does not capture `itemgetter`/`methodcaller` arguments; they are re-evaluated per element.
   - p14: `sorted(rows, key=itemgetter(idx(), 1))`; expected `multi [('a',10),('b',20),('c',30)]` / `calls 1`; actual `TypeError: '<' not supported between instances of 'str' and 'int'`, exit 1.
2. Inline `map()`/`filter()` path does not capture bound arguments at callable construction (CPython map/filter are lazy).
   - p16b: `m=map(itemgetter(i),rows); i=1; list(m)` expected `['a','b','c']`, actual `[10,20,30]`; `f=filter(methodcaller("endswith",s),names); s=".txt"` expected `['a.md','c.md']`, actual `['b.txt']`.
   - p15: side-effecting suffix expected `['a.md','c.md']` / `calls 1`, actual all three / `calls 3`.
3. `countOf`/`indexOf` use Python iteration (`for item in seq`), so a sequence that only implements `__getitem__` (valid for CPython `PySequence_Count`/`PySequence_Index`) crashes.
   - p18: expected `cnt_custom 2 1` etc.; actual `TypeError: 'Seq' object is not iterable`, exit 1.

VERDICT: FIX

1. Capture `itemgetter`/`methodcaller` arguments in the inline `key=` lowering (p14: expected sorted rows / calls 1, actual TypeError exit 1).
2. Capture bound arguments in inline `map()`/`filter()` at construction time (p16b: expected `['a','b','c']` and `['a.md','c.md']`, actual `[10,20,30]` and `['b.txt']`; p15: expected `['a.md','c.md']` / calls 1, actual all names / calls 3).
3. Make `countOf`/`indexOf` use the sequence indexing protocol (or refuse by name) instead of `for item in seq` for `__getitem__`-only sequences (p18: expected `cnt_custom 2 1`, actual `TypeError: 'Seq' object is not iterable`).
[cost $0.0284, opencode tokens {"total": 1001447, "input": 54417, "output": 10308, "reasoning": 18834, "cache.write": 0, "cache.read": 917888}]
    tool time: bash 24.5 min
        709s bash   cd /home/runner/work/_temp/w2 && rm -rf /tmp/mpA /tmp/mpB && mkdir -p /tmp/mpA /tmp/mpB && for t in berth_sim 
        303s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 2400 python3 ../tools/par_check.py -j 2 test_ail_std_oper
        132s bash   cd /home/runner/work/_temp/w2 && rm -rf /tmp/dbgA /tmp/dbgB && mkdir -p /tmp/dbgA /tmp/dbgB && for t in berth_
         74s bash   cd /tmp && rm -rf dbg_head dbg_base && mkdir -p dbg_head dbg_base && cd /home/runner/work/_temp/w2 && for t in
         62s bash   cd /home/runner/work/_temp/w2 && for p in p7_is_ident p8_inline_sideeffect p9_setdel2 p10_item2 p11_mc2; do ec
         57s bash   cd /home/runner/work/_temp/w2 && for p in p_errors p_scan_values p_scan_values2 p_mutation_targets p_loop_item
         34s bash   cd /home/runner/work/_temp/w2 && for p in p13_key_single p14_key_multi p15_mc_filter p16_map_lazy p17_is_plain
         23s bash   cd /home/runner/work/_temp/w2 && for p in p1_scan p2_item p3_attr_meth p4_setdel p5_truth_is p6_noop; do echo 

FINAL VERDICT: FIX  2026-11-01T11:39:01Z
