# job job-std_textwrap-11011435  started 2026-11-01T05:36:09Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Done. Commit `fd1e2cb` on `job-std_textwrap-11011435`.

- **Programs:** 12/12 in `lab/stdlib/textwrap/` build and match CPython stdout + exit code on the default and forced-general builds. All 12 take the general path (helper `__init__` defaults); this is recorded in `lab/stdlib/textwrap/RESULTS.md`, not a refusal.
- **Fix:** common `wrap`/`fill`/`shorten` keyword options and `textwrap.TextWrapper` are now built via `_ail_TextWrapper`; duplicate `width` stays refused by name.
- **Probes:** `p_tw_opts`, `p_tw_class`, `p_tw_shorten`, `p_tw_indent`, `p_tw_types`, `p_tw_hyphen`, `p_tw_maxlines`, `p_tw_sentence`, `p_tw_widths` — all match CPython on both builds, covering options, construction/mutation, empty text, widths -5..70, placeholder errors, non-str values, list/attribute/dict sources, tabs, hyphens, sentence endings.
- **Tests on final commit:** `test_ail_std_textwrap`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_stdlib1`, `test_ail_stdlib25`, `test_ail_stdlib31` all pass.
- **Manifest:** `python3 tools/update_manifest.py --check` passes.
- **lab/compare:** generated C unchanged for all 10 tasks (7 normal builds, 2 with `--exact-int`; 3 fail identically on both revisions).
- **Follow-ups in RESULTS.md:** subclassing `TextWrapper` (`not in the subset: a non-name base class in class MyWrapper`), `wordsep_re=` (`not in the subset: _ail_TextWrapper() called with an unknown keyword argument wordsep_re`), and the typed fast path.
[cost $0.0320, opencode tokens {"total": 2360847, "input": 78402, "output": 11175, "reasoning": 11302, "cache.write": 0, "cache.read": 2259968}]
    tool time: bash 33.8 min, edit 0.0 min, write 0.0 min
        551s bash   mkdir -p /tmp/finaltests && cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && run(){ python3 -B "$1" > "/tmp/f
        389s bash   rm -rf /tmp/base_ail /tmp/cmpc && cp -a /home/runner/work/ail-ci/ail-ci/AIL_CURRENT /tmp/base_ail && git -C /h
        277s bash   cd AIL_CURRENT && timeout 1800 python3 -B test_ail_std_textwrap.py 2>&1 | tail -80
        264s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && run(){ python3 -B "$1" > "/tmp/finaltests/$1.log" 2>&1; echo
        148s bash   cat > /tmp/probes/p_tw_opts.py <<'EOF' import textwrap  text = "The quick brown fox jumps over the lazy dog. A
        145s bash   mkdir -p /tmp/twbuild && cd /tmp/twbuild && for f in /home/runner/work/ail-ci/ail-ci/lab/stdlib/textwrap/*.py;
        130s bash   cd /tmp/probes && for p in p_tw_opts p_tw_class p_tw_shorten p_tw_indent p_tw_types p_tw_hyphen p_tw_maxlines 
        106s bash   cd /tmp/cmpc && ok=1; for t in chain_relax rail_transfer; do AIL_NO_CACHE=1 PYTHONDONTWRITEBYTECODE=1 python3 

## review 0
[model opencode-go/deepseek-v4.1-flash]
Review of `work..HEAD` (`fd1e2cb`).

**What the change does:** replaces the typed lowering of `textwrap.wrap/fill/shorten` with a generated `_ail_TextWrapper` Python class accepting the common options and `TextWrapper`, and updates the tests/docs accordingly.

**Probes** (run with `cmp.sh` against HEAD, and base where noted):
- `p1_opts.py` — options, keyword/positional forms, empty text, widths 0/-3, shorten, errors: **default and general match CPython**.
- `p2_class.py` — construction, mutation, value sources, positional args: **default and general DIFF at the keyword-only boundary** (below).
- `p3_matrix.py` — option/text matrix via `**opts`: **named compile refusal** (`textwrap.fill() with these arguments is not built`); acceptable.
- `p4_types.py` — None/int/float/bytes/list, None/float/str/bool width, tabs, errors: **both builds match CPython**.
- `p5_cases.py` — duplicate width/text, unknown keyword, `*args`/`**kwargs`, shorten duplicates: **named refusals**, no crash.
- Base run of `p2_class.py`: base refuses `TextWrapper` by name, so the difference below is introduced by this change, not pre-existing.
- On the worker's `/tmp/cmpc` artifacts, generated `program.c` for `berth_sim`, `echo_pack`, `ledger_bin`, `term_rank`, `ticket_audit` is identical between base and HEAD.

**Defect**
1. `_ail_TextWrapper.__init__` makes `max_lines` and `placeholder` positional, but CPython 3.12 makes them keyword-only. For
   ```python
   import textwrap
   print(textwrap.TextWrapper(8, "", "", True, True, False, True, True, True, 8, 2, "..").wrap("ab cd ef gh"))
   ```
   Expected (CPython): `TypeError: TextWrapper.__init__() takes from 1 to 11 positional arguments but 13 were given` (exit 1).
   Actual (HEAD, default and general): `['ab cd ef', 'gh']` (exit 0).

**Report claims**
- 12/12 build and match CPython on default/general: **verified** (`test_ail_std_textwrap` passed).
- Common options + `TextWrapper` build; duplicate `width` refused: **verified** (stdlib1/25/31 passed), except the keyword-only mismatch above.
- All 12 take the general path: **verified** (`RESULTS.md` and test output).
- Listed tests pass: **verified** — `test_ail_std_textwrap`, `test_ail_safetynet`, `test_ail_stdlib1/25/31` all pass (`-j 2`, 528s).
- `update_manifest.py --check`: **verified** (exit 0).
- Worker `p_tw_*` probes: **not rerun** (present in `/tmp/probes`; my `p1`/`p4` equivalents match).
- lab/compare C byte-identical for all 10: **partially verified** (5 successful tasks checked; remaining 5 not rerun).

**Pre-existing:** none: CPython also loops forever on some negative-effective-width configurations (e.g. `TextWrapper(width=1, subsequent_indent="abc", drop_whitespace=False).wrap('ab"')`), so that is not attributed to this change.

**Unverified:** full lab/compare set, `test_ail_files`/`test_ail_corpus_findings3`, and instruction-count impact (the change forces all textwrap calls to the general path; correctness is unaffected).

VERDICT: FIX
1. Make `max_lines` and `placeholder` keyword-only in `_ail_TextWrapper.__init__` (matching CPython), so passing them positionally is a `TypeError`/named refusal rather than accepted output. Probe and expected/actual as in Defect 1 above.
[cost $0.0310, opencode tokens {"total": 1575044, "input": 73511, "output": 12779, "reasoning": 13170, "cache.write": 0, "cache.read": 1475584}]
    tool time: bash 25.1 min
        529s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 620 python3 ../tools/par_check.py -j 2 test_
        400s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p3_matrix p4_types; do (bash ~/tools/cmp.sh /tmp/rprobes/$p.py 
        126s bash   cd /home/runner/work/ail-ci/ail-ci && date; for p in p1_opts p2_class; do (bash ~/tools/cmp.sh /tmp/rprobes/$p
        120s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 - <<'EOF' import ail_syntax, textwrap, random, strin
        115s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 115 python3 - <<'EOF' import ail_syntax, textwrap, r
        100s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 100 python3 -u - <<'EOF' import ail_syntax, textwrap
         62s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 110 python3 -u - <<'EOF' import ail_syntax, textwrap
         20s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 20 python3 -u - <<'EOF' > /tmp/hangtrace.txt 2>&1 im

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed the review defect in `AIL_CURRENT/ail_syntax.py:1247`: `_ail_TextWrapper.__init__` now has `*` before `max_lines` and `placeholder`, matching CPython 3.12's keyword-only boundary.

**Probes** (`bash ~/tools/cmp.sh`, default + general):
- `p_kwonly` (12 positional): CPython exit 1; AIL named refusal `_ail_TextWrapper() called with too many positional arguments`.
- `p_kw_pos11` (11 positional): CPython exit 1; same named refusal.
- `p_kw_pos12`: CPython exit 1; same named refusal.
- `p_kw_boundary`: 10 positional args, keyword forms, mutation, and values via list item/attribute/dict/function arg — **both builds match CPython**.
- `p_kw_alias`: refused by name (`TextWrapper used as a plain value`), pre-existing.

**Tests** (final content, `par_check.py -j 2`): `test_ail_std_textwrap`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_stdlib1`, `test_ail_stdlib25`, `test_ail_stdlib31` — **7/7 passed** (795s).

**Other checks:** `update_manifest.py --check` exit 0; generated C for all 10 `lab/compare` `main.ail` tasks is byte-identical to base.

Committed as `755e806`.
[cost $0.0171, opencode tokens {"total": 945154, "input": 48858, "output": 6358, "reasoning": 5458, "cache.write": 0, "cache.read": 884480}]
    tool time: bash 23.7 min, edit 0.0 min, read 0.0 min
        797s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1500 python3 ../tools/par_check.py -j 2 test
        368s bash   set -e cd /home/runner/work/ail-ci/ail-ci rm -rf /tmp/base_tree /tmp/c_cmp && mkdir -p /tmp/base_tree /tmp/c_c
         74s bash   cd /home/runner/work/ail-ci/ail-ci && for t in chain_relax rail_transfer scar_life tally_lang tree_fold; do fo
         71s bash   set -e cd /home/runner/work/ail-ci/ail-ci rm -rf /tmp/c_ail && mkdir -p /tmp/c_ail for t in $(ls lab/compare/t
         38s bash   cat > /tmp/probes/p_kw_boundary.py <<'EOF' import textwrap  w = textwrap.TextWrapper(8, "", "", True, True, Fa
         32s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p_kwonly p_kwonly_ok; do echo "=== $p ==="; bash ~/tools/cmp.sh
         26s bash   cat > /tmp/probes/p_kw_boundary.py <<'EOF' import textwrap  W = textwrap.TextWrapper w = W(8, "", "", True, Tr
         11s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/dbgtest && mkdir -p /tmp/dbgtest && AIL_NO_CACHE=1 python3 A

## review 1
[model opencode-go/deepseek-v4.1-flash]
**Review report** (work..HEAD = `fd1e2cb` + `755e806`)

**What the change really does.** The diff (larger than the report, which describes only `755e806`) adds a Python reimplementation of `textwrap.TextWrapper` in `ail_syntax._MATH_HELPERS['tw_class']`, lowers `textwrap.wrap/fill/shorten/TextWrapper` through it with all common options, adds the 12 lab programs + `test_ail_std_textwrap`, and edits the stdlib1/25/31 refusal tests. `755e806` only adds `*` before `max_lines`/`placeholder`.

**Probes** (all `bash ~/tools/cmp.sh`, default + general):

| probe | result |
| --- | --- |
| `p_pos10` (10 positional args, wrap) | both builds match CPython |
| `p_pos11` (11 positional args) | CPython TypeError; AIL named refusal (`too many positional arguments`) — acceptable |
| `p_routes` (wrap/fill/shorten text & width positional/keyword, defaults, no-arg TextWrapper) | both match |
| `p_opts` (options via args/list item/attribute/dict value, hyphen/tab/sentence flags) | both match |
| `p_edge` (empty/whitespace, width 1, max_lines 0/1/2, invalid width, placeholder too large, shorten edges) | both match CPython (same exit 1 / same stdout) |
| `p_mutation` (mutate width/indents/max_lines/placeholder, reuse) | both match |
| `p_fuzz` (31 tricky strings × many option combinations, 337 lines) | both match |
| `p_fromimport`, `p_nonuse`, `p_floatwidth` | both match |
| `p_dupkw_class` (duplicate ctor keyword) | named refusal — acceptable |
| **`p_shorten` / `p_dup_ml`** | **DEFECT** (below) |

Also verified: non-user program C is byte-identical base vs HEAD (`--debug-dir`, only report temp paths differ); no `textwrap` in `lab/compare/src`, so those C files cannot change; `update_manifest.py --check` exit 0.

**Defect 1 — `shorten` ignores a duplicate `max_lines` instead of raising.**
```python
import textwrap
try:
    print(repr(textwrap.shorten("a b c d e f", width=10, max_lines=2)))
except TypeError as exc:
    print("TypeError", str(exc))
```
Expected (CPython 3.12, both builds of HEAD differ): `TypeError textwrap.TextWrapper() got multiple values for keyword argument 'max_lines'`
Actual (AIL default and general): `'a b c d e\nf'`
`shorten` injects `max_lines=1` then forwards the caller's `max_lines`, and the duplicate keyword is silently overwritten. On the base this program is refused by name, so the change caused the wrong output. Fix: reject that extras case by name, or raise the TypeError.

**Claims in the report.**
- Keyword-only boundary (`*` before `max_lines`/`placeholder`): verified (`p_pos10` accepts 10, `p_pos11` refuses; CPython agrees).
- “p_kw_boundary / p_kw_alias”: not re-run; marked unverified (my `p_opts`/`p_mutation` cover the same behaviours).
- “7/7 tests passed”: I ran the changed modules + safetynet — `test_ail_std_textwrap`, `test_ail_stdlib1`, `test_ail_stdlib25`, `test_ail_stdlib31`, `test_ail_safetynet`: 5/5 passed (442 s, `-j 2`). `test_ail_files`/`test_ail_corpus_findings3` not re-run (unverified).
- `update_manifest --check` exit 0 and 10-compare-C identity: verified (C identity via non-user probe + no textwrap imports in compare sources).
- Report omits that work..HEAD contains the whole feature, not just the keyword-only fix.

**Pre-existing:** `**kwargs` call arguments and module-level dicts are still refused (same on base); CPython itself hangs on the `drop_whitespace=False`, width−indent < 0, empty-chunk case, and AIL matches that behaviour (not a defect).

**Unverified:** `test_ail_files`, `test_ail_corpus_findings3`, the worker's own `p_kwonly`/`p_kw_alias` probes, and full 10-task compare builds.

VERDICT: FIX
1. `textwrap.shorten(..., max_lines=N)` silently uses `N` instead of raising CPython's `TypeError: textwrap.TextWrapper() got multiple values for keyword argument 'max_lines'` (probe `p_dup_ml.py`; both default and general builds).
[cost $0.0382, opencode tokens {"total": 2037756, "input": 80547, "output": 13951, "reasoning": 19930, "cache.write": 0, "cache.read": 1923328}]
    tool time: bash 17.0 min
        443s bash   date && cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1400 python3 ../tools/par_check.py -j 2 test
        120s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 - <<'EOF' import ail_syntax, textwrap, random ns={};
        102s bash   cd /tmp/rprobes && python3 - <<'EOF' p='p_edge.py' s=open(p).read() s=s.replace('def try_wrap(label, text, wid
         90s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 90 python3 -u - <<'EOF' import ail_syntax, textwrap,
         72s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p_pos10 p_opts p_edge p_shorten p_mutation p_nonuse; do echo "=
         53s bash   cd /tmp/rprobes && cat > p_dup_ml.py <<'EOF' import textwrap  def main() -> None:     try:         print("A", 
         30s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p_fuzz p_fromimport; do echo "==== $p ===="; bash ~/tools/cmp.s
         26s bash   cd /tmp/rprobes && python3 - <<'EOF' p='p_fuzz.py' s=open(p).read() s=s.replace('    try:\n        print(repr(

FINAL VERDICT: FIX  2026-11-01T08:24:51Z
