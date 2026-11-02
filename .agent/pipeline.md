# job job-prog29-11022055  started 2026-11-02T11:56:07Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed as `03684d3`.

- **Defect:** `len({...})` over a mutable source whose element/filter runs code now raises a named compile-time refusal instead of silently using the eagerly snapshotted sequence. Default build falls back and matches CPython (`3 3`); `--strict` names the refusal.
- **Probes:** `p_sc_mutate_attr`, `p_sc_mutate_alias`, `p_sc_mutate_elt` all match CPython under the default build; `p_sc_dict_mutate`, `p_sc_field_nocode`, `p_sc_str_call_filter` match/refuse as expected. `p_lc_mutate_attr` and `p_manual_for_mutate` still show the pre-existing field-snapshot difference, unchanged by this commit.
- **Tests:** `test_ail_prog29`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed.
- **Manifest:** `update_manifest.py` run and `--check` clean.
- Corrected the inaccurate report rows in `lab/progfix/prog29.md` and added a DEVLOG entry.
[cost $0.0000, opencode tokens {"total": 2481278, "input": 88359, "output": 8093, "reasoning": 13114, "cache.write": 0, "cache.read": 2371712}]
    tool time: bash 6.4 min
        346s bash   python3 tools/par_check.py -j 2 test_ail_prog29 test_ail_safetynet test_ail_files test_ail_corpus_findings3 2>
         20s bash   cat > /tmp/probes29/p_sc_mutate_alias.py <<'EOF' class Box:     def __init__(self) -> None:         self.xs: l
          8s bash   mkdir -p /tmp/probes29 && cat > /tmp/probes29/p_sc_mutate_attr.py <<'EOF' class Box:     def __init__(self) ->
          4s bash   bash .agent/cmp.sh /tmp/probes29/p_sc_mutate_attr.py $PWD; echo ===STRICT; cd /tmp/probes29 && AIL_NO_CACHE=1 
          1s bash   cd /tmp && rm -rf g17t && mkdir g17t && cd g17t && cp /home/runner/work/ail-ci/ail-ci/lab/census/programs/gdev
          1s bash   python3 tools/update_manifest.py && python3 tools/update_manifest.py --check && git status --short
          0s bash   python3 tools/par_check.py -j 2 test_ail_prog29 test_ail_safetynet test_ail_files test_ail_corpus_findings3 2>
          0s bash   cat .agent/pipeline.md 2>/dev/null | head -50; ls lab/progfix/ | tail; git show --stat HEAD | head -40

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review of prog29 review-fix

**What the change does:** adds a compile-time guard in `_setcomp_len` (`pyfunc.py`) refusing `len({e for v in seq if c})` when the element/filter contains a call-like node and the source is (supposedly) a mutable container; updates the test, DEVLOG and prog29 doc.

**Verified**
- Exact review defect now fixed: `p_sc_mutate_attr.py` HEAD default `3 3`; base default `2 3`; `--strict` names the new refusal.
- `p_sc_mutate_{alias,elt,local,arg}`, `p_sc_dict_mutate`, `p_sc_field_nocode`, `p_sc_str_call_filter`, walrus and pure-call probes match CPython on HEAD.
- `tree_fold` and `ledger_bin` `--debug-dir` `program.c` byte-identical base vs HEAD (sampled; no lab/compare source uses `len({`).
- `test_ail_prog29 test_ail_safetynet test_ail_files test_ail_corpus_findings3`: 4 modules, 0 failed. `update_manifest.py --check` clean.
- `g17_026` still builds strict and matches CPython (via `test_ail_prog29`).

**False / inaccurate claims**
- DEVLOG/report says the refusal covers "a mutable list, float list, str list, set or dict". It does not cover typed set fields: `_setcomp_source_can_change` tests `source_type in (LIST, FLIST, SLIST, SET, DICT)` but a `set[int]`/`set[str]` field is `ISET`/`SSET` (typed dict kinds are `IDICT`/`SDICT`/…, not `DICT`).
- "The default build falls mixed-mode back to CPython for the refused function" is inaccurate: the default build is not the CPython hybrid, and for a typed set field it does not fall back at all.

**Pre-existing**
- `p_lc_mutate_attr.py` and `p_manual_for_mutate.py`: default `2 3` vs CPython `3 3`; identical on base.
- `p_sc_mutate_setfield.py` also differs identically on base, but the new guard claims set coverage and does not fire (see defect).

**Defect**
1. Typed set-field source is not refused. Probe `/tmp/rprobes/p_sc_mutate_setfield.py`:
```python
class Box:
    def __init__(self) -> None:
        self.s: set[int] = set()
    def side(self) -> bool:
        if len(self.s) < 3:
            self.s.add(99)
        return True

def f(box: Box) -> int:
    return len({x for x in box.s if box.side()})

def main() -> None:
    box = Box()
    box.s.add(1); box.s.add(2)
    print(f(box), len(box.s))
main()
```
Expected (CPython): exit 1, `RuntimeError: Set changed size during iteration`. Actual HEAD default **and** `--strict`: exit 0, stdout `2 3` (no refusal). The guard must also match `ISET`/`SSET` (and typed dict kinds). This is the same mutation-during-walk class the change is meant to refuse and the task forbids a silent difference.

**Unverified**
- The other seven programs' first blockers (unchanged by this diff).
- The other eight lab/compare C outputs (only two sampled).
- The doc-only rows about shadowed `len` / annotated-frozenset parameter (relied on review 1).
- Instruction counts (not needed: compile-time-only change).

VERDICT: FIX
1. `_setcomp_source_can_change` misses typed set/dict kinds (`ISET`, `SSET`, `IDICT`, `SDICT`, …), so `p_sc_mutate_setfield.py` builds and prints `2 3` at exit 0 in both default and strict builds where CPython raises `RuntimeError` at exit 1. Extend the kind check to the typed set/dict kinds.
[cost $0.0000, opencode tokens {"total": 2107781, "input": 74427, "output": 8875, "reasoning": 24863, "cache.write": 0, "cache.read": 1999616}]
    tool time: bash 6.9 min, write 0.0 min
        275s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1600 python3 ../tools/par_check.py -j 2 test_a
         22s bash   date; cd /tmp/rprobes; for p in p_sc_mutate_setlocal p_sc_mutate_dictlocal p_sc_mutate_untypedset p_sc_mutate_
         20s bash   date; cd /tmp/rprobes; for p in p_sc_pure_intlist p_sc_pure_strlist p_sc_pure_floatlist p_sc_pure_field; do ec
         16s bash   date; cd /tmp; rm -rf cmpA cmpH cmpAB cmpHB; for t in tree_fold ledger_bin; do for who in A H; do if [ $who = 
         13s bash   date; cd /tmp/probes29; for p in p_sc_dict_mutate p_sc_field_nocode p_sc_str_call_filter p_sc_mutate_alias p_s
         13s bash   date; cd /tmp/rprobes; for p in p_sc_walrus_filter p_sc_walrus_elt; do echo "===== $p HEAD"; bash ~/tools/cmp.
         12s bash   date; cd /tmp/rprobes; for p in p_sc_inline_untyped_set p_sc_inline_typed_set; do echo "===== $p HEAD"; bash ~
         11s bash   date; cd /tmp/rprobes; for p in p_sc_mutate_attr p_sc_mutate_arg p_sc_mutate_local p_sc_mutate_olist; do echo 

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed as `40ec90c`.

- `_setcomp_source_can_change` now matches all typed set/dict kinds via `MAPS` (`ISET`, `SSET`, `IDICT`, `SDICT`, …).
- Reviewer probe `p_sc_mutate_setfield.py`: was `2 3` exit 0; now both builds exit 1 with CPython's `RuntimeError: Set changed size during iteration`.
- Also re-ran `p_sc_mutate_{dictfield,setlocal,dictlocal,attr,arg,local,elt,olist,strlist,untypedset,untypeddict}`, pure-field, walrus, inline, and typed-dict-call probes: all match CPython or are refused by name.
- Added typed-set-field and typed-dict-source regression cases to `test_ail_prog29`.
- `test_ail_prog29 test_ail_safetynet test_ail_files test_ail_corpus_findings3`: 4 modules, 0 failed. `update_manifest.py --check` clean.
- No `lab/compare` source uses `len({`, so generated C is unaffected.
[cost $0.0000, opencode tokens {"total": 1776862, "input": 170411, "output": 8756, "reasoning": 7167, "cache.write": 0, "cache.read": 1590528}]
    tool time: bash 10.7 min, edit 0.0 min
        273s bash   timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_prog29 test_ail_safetynet test_ail_files test_ail_cor
        272s bash   timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_prog29 test_ail_safetynet test_ail_files test_ail_cor
         58s bash   for p in /tmp/rprobes/p_sc_*.py; do b=$(basename "$p" .py); echo "===== $b"; bash ~/tools/cmp.sh "$p" $PWD; do
         21s bash   for p in p_sc_mutate_setfield p_sc_mutate_dictfield p_sc_mutate_setlocal p_sc_mutate_dictlocal p_sc_mutate_att
          8s bash   for p in p_sc_mutate_setfield p_sc_mutate_dictfield p_sc_mutate_setlocal; do echo "===== $p"; bash ~/tools/cmp
          3s bash   cat > /tmp/rprobes/p_sc_typed_dict_call.py <<'EOF' def keep(k: str) -> bool:     return len(k) > 0  def f() ->
          2s bash   bash ~/tools/cmp.sh /tmp/rprobes/p_sc_pure_setfield.py $PWD
          1s bash   cat > /tmp/rprobes/p_sc_pure_setfield.py <<'EOF' class Box:     def __init__(self) -> None:         self.s: se

## review 1
[model opencode/deepseek-v4.1-flash-free]
## Review of prog29 fix (commits 03684d3, 40ec90c)

**What the change really does:** adds a static guard in `pyfunc._setcomp_len`: when `len({elt for v in src if cond})` has a call/walrus/lambda/await/yield in `elt` or a filter and `src` is a mutable typed/untyped list/set/dict (or a dict keys/values snapshot), it is a named compile-time refusal; otherwise the eager lowering is unchanged. Defends against the eager lowering snapshotting a source that CPython's iterator would observe changing.

**Claims checked**
- `_setcomp_source_can_change` now covers typed set/dict kinds via `MAPS`: **verified** by code (`pyfunc.py:136`, `:19634`) and probes.
- Reviewer probe `p_sc_mutate_setfield.py` was `2 3` exit 0, now both builds exit 1 with `RuntimeError: Set changed size during iteration`: **verified** (base default `2 3` exit 0; HEAD both builds exit 1).
- Previous review defect `p_sc_mutate_attr.py`: base default `2 3`; HEAD default `3 3`, strict refuses by name: **verified**.
- Typed-set-field and typed-dict-source regression cases added to `test_ail_prog29`: **verified** in source.
- `test_ail_prog29 test_ail_safetynet`: 2 modules, 0 failed; `update_manifest.py --check` clean: **verified**.
- `test_ail_files`, `test_ail_corpus_findings3` 0 failed: **not re-run** (review scope).
- No `lab/compare` source uses `len({`; generated C unaffected: **verified** by grep; baseline and pure-list `--debug-dir` `program.c` byte-identical HEAD vs base.
- Claim that typed *dict* sources "slipped through": **false/inaccurate**. Base already refused `dict` sources (`'d' is a sdict; only ... walked as flat sequences`); only typed **set fields** were actually accepted-and-wrong. The MAPS addition is harmless future-proofing and changes the refusal message, not build acceptance.

**Own probes** (all `bash ~/tools/cmp.sh`, HEAD)
- `rv2_olist_{param,local,}_mutate`, `rv2_srows_mutate`, `rv2_bytearray_mutate`, `rv2_blist_mutate`: match CPython (these source kinds are live/iterated or refused elsewhere).
- `rv2_mutate_local_list`, `_list2`, `rv2_flist_mutate`, `rv2_slist_mutate`, `rv2_dict_local_mutate`, `rv2_dictfield_mutate`: strict refusal by the new guard; default build matches CPython (including `RuntimeError` exit 1 for dicts).
- `rv2_pure_list`, `rv2_str_call`, `rv2_bytes_call`, `rv2_setfield_purecall`, `rv2_listfield_purecall`, `rv2_baseline`: default and strict match CPython; C unchanged where the feature is not used.
- Broad refusal of harmless calls over mutable sources is over-conservative but named, and the default/general path matches CPython, so not a defect.

**Pre-existing:** none observed — every probe that differed on base was the defect this change fixes.

**Unverified:** instruction counts (change is compile-time only); `test_ail_files` / `test_ail_corpus_findings3` results (not in review scope).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 2068513, "input": 191067, "output": 9681, "reasoning": 19061, "cache.write": 0, "cache.read": 1848704}]
    tool time: bash 5.1 min
        175s bash   date -u; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 tes
         32s bash   cd /tmp/rprobes && cat > rv2_bytearray_mutate.py <<'EOF' def side(ba: bytearray) -> bool:     if len(ba) < 3: 
         23s bash   cd /tmp/rprobes && for p in p_sc_mutate_attr rv2_olist_mutate rv2_mutate_local_list rv2_mutate_local_list2 rv2
         12s bash   cd /tmp/rprobes && cat > rv2_tuple_call.py <<'EOF' def ok(x: int) -> bool:     return x >= 0  def f(xs: tuple[
         12s bash   cd /tmp/rprobes && for p in p_sc_mutate_untypedset p_sc_mutate_untypeddict p_sc_mutate_olist p_sc_mutate_strli
         11s bash   cd /tmp/rprobes && for p in p_sc_mutate_setfield p_sc_mutate_dictfield p_sc_pure_setfield p_sc_typed_dict_call
          7s bash   cd /tmp/rprobes && for p in p_sc_mutate_attr p_sc_mutate_setfield p_sc_pure_setfield; do echo "===== $p BASE";
          7s bash   cd /tmp/rprobes && cat > rv2_setfield_purecall.py <<'EOF' class Box:     def __init__(self) -> None:         s

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-02T13:56:48Z
