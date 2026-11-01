# job job-std_fractions-11011614  started 2026-11-01T07:15:24Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Done. Final state is committed on `job-std_fractions-11011614`.

**Results**
- 12/12 `lab/stdlib/fractions` programs build in default mode (general path) and match CPython 3.12 stdout + exit code.
- Fixed 3 general-path bugs: Fraction division-by-zero message denominator, `round(number=, ndigits=)` handling, and tuple-key `KeyError.args[0]`.
- No follow-ups required. `RESULTS.md` records the first-build outcomes and fixes.

**Verification**
- Tests: `test_ail_std_fractions`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_exc_str`, `test_ail_tuples` — 6/6 passed.
- `python3 tools/update_manifest.py` — no changes; `--check` passes.
- Compare tasks: all 10 `main.ail` generated-C hashes are identical to base `dafa966`; no compare `main.py` contains the changed constructs, and the exercisable raw build (`echo_pack`) was identical.
- Probes with `cmp.sh` (both builds): `p_fraction_div`, `fr_div_zero`, `p_round_kw`, `round_kw`, `p_keyerror_tuple`, `p_keyerror_scalars`, `keyerror_keys`, `keyerror_multi`, `tuple_no_handler` all matched CPython. Refusal probes `round_bad_missing`, `round_bad_dup`, `round_bad_extra`, `p_round_refusal` were refused by name in both builds.

Commits: `784313a` (work + fixes), `3921531` (test manifest pins). Working tree has only the harness-created `.agent/pipeline.md`.
[cost $0.0254, opencode tokens {"total": 2002981, "input": 68098, "output": 5950, "reasoning": 9701, "cache.write": 0, "cache.read": 1919232}]
    tool time: bash 10.6 min
        451s bash   python3 tools/par_check.py -j 2 test_ail_std_fractions test_ail_safetynet test_ail_files test_ail_corpus_findi
         83s bash   cd /home/runner/work/ail-ci/ail-ci && for p in fr_div_zero keyerror_keys keyerror_multi round_kw tuple_no_hand
         40s bash   for t in berth_sim chain_relax echo_pack ledger_bin rail_transfer scar_life tally_lang term_rank ticket_audit 
         29s bash   cat > /tmp/cmp_pyboxed.py <<'PY' import sys, hashlib, json root = sys.argv[1] src = open(sys.argv[2], encoding
         17s bash   cd /home/runner/work/ail-ci/ail-ci && for p in round_bad_missing round_bad_dup round_bad_extra p_round_refusal
          9s bash   python3 tools/codegen_diff.py --base dafa966 --source "$(cat lab/compare/src/berth_sim/main.ail)" 2>&1 | head 
          3s bash   cat > /tmp/probes/p_keyerror_scalars.py <<'PY' def check(d, k):     try:         return d[k]     except KeyErr
          1s bash   grep -rn "KeyError as\|round(.*number\|round(.*ndigits" lab/compare/src/*/main.py || echo "no bound KeyError /

## review 0
[model opencode-go/deepseek-v4.1-flash]
## Review: std_fractions

**What the diff really does:** adds 12 `fractions` lab programs + a CPython-comparison test/registration; fixes the prelude's Fraction-division zero message (`da`→`db`); teaches the general `round()` builtin `number=`/`ndigits=`; and makes tuple-table `KeyError` keep the raw key as `args[0]` when the program binds a KeyError handler. Matches the report except that it omits the new evaluation-order regression.

**Probes** (`/tmp/rprobes/`, cmp.sh, both `g` and `d` builds vs CPython; base `/tmp/base` = `work`):
- `fr_div_zero.py`, `key_tuple.py`, `key_scalar_mixed.py`, `key_bool_float.py`, `key_multi_*`, `key_val_tuple_*`, `set_tuple_remove.py`, `no_feature.py` — HEAD all match CPython. Base differs only on the old div-zero message and on `key_except_tuple`/`probability` (both fixed here).
- `round_kw.py` — HEAD matches.
- `round_eval_order.py` — **HEAD differs** (below).
- Refusals `round(ndigits=2)`, `round(1, number=2)`, `round(1, foo=2)` — refused by name as reported.
- `no_feature.py`: generated `program.c` byte-identical base vs HEAD. All 10 compare-task `main.ail` codegen hashes identical (codegen_diff, base `dafa966`).
- Tests: `test_ail_std_fractions` and `test_ail_safetynet` pass (237s, 0 failed). `update_manifest.py --check` passes.

**Claims:** 12/12 build+match = verified; three fixes = verified; compare-task C identical = verified (10/10); manifest = verified; 6/6 tests = only the 2 required modules re-run, other 4 unverified; no follow-ups = false (see defect); probes/refusals = verified.

**Defect (introduced by this change — base refuses the program, so not pre-existing):**
1. `round()` evaluates keyword arguments in the wrong order when `ndigits` is written before `number`. The new code always lowers `number` first, ignoring source order; CPython evaluates call keywords left-to-right.
```python
def num():
    print("eval number"); return 2.5
def dig():
    print("eval ndigits"); return 1
print("A", round(number=num(), ndigits=dig()))
print("B", round(ndigits=dig(), number=num()))
```
Expected (CPython, both builds):
```
eval number / eval ndigits / A 2.5 / eval ndigits / eval number / B 2.5
```
Actual (HEAD, both builds):
```
eval number / eval ndigits / A 2.5 / eval number / eval ndigits / B 2.5
```
Named output values are still `A 2.5`, `B 2.5`, but side effects occur in the wrong order. Fix by lowering keyword values in `kwargs` insertion (source) order.

**Pre-existing:** none observed that still differ on HEAD.

**Unverified:** `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_exc_str`, `test_ail_tuples` (not re-run per instructions); speed (change is compile-time/cold paths, no runtime hot-code change).

VERDICT: FIX
[cost $0.0385, opencode tokens {"total": 2527042, "input": 70856, "output": 10817, "reasoning": 23609, "cache.write": 0, "cache.read": 2421760}]
    tool time: bash 20.1 min
        238s bash   cd /home/runner/work/ail-ci/ail-ci && date && python3 tools/par_check.py -j 2 test_ail_std_fractions test_ail_
        155s bash   cd /home/runner/work/ail-ci/ail-ci && for p in key3_prob key_str_elem key_tuple_tuple key_except_tuple key_bar
        121s bash   cd /tmp/base && for p in key3_prob key_str_elem key_tuple_tuple key_except_tuple key_bare_handler; do echo "##
        108s bash   cat > /tmp/rprobes/key_scalar_tuplib.py <<'PY' from fractions import Fraction  def main():     d = {}     for 
         92s bash   cd /tmp && rm -rf dbgbase dbghead && mkdir -p /tmp/workbase /tmp/workhead cd /tmp/workbase && AIL_NO_CACHE=1 p
         88s bash   cat > /tmp/rprobes/key_multi_str.py <<'PY' from fractions import Fraction  def main():     out = {}     for r 
         71s bash   cd /tmp/base && bash ~/tools/cmp.sh /home/runner/work/ail-ci/ail-ci/lab/stdlib/fractions/probability.py "$PWD"
         61s bash   cat > /tmp/rprobes/key_fn_tuple.py <<'PY' from fractions import Fraction  def main():     outcomes = {}     fo

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed the review defect and committed as `159be24`.

- `pyboxed2._b_round` now lowers keyword values in source/insertion order, so `round(ndigits=dig(), number=num())` matches CPython's `dig()` then `num()`.
- Added the both-orders + mixed positional/keyword regression to `test_ail_std_fractions`.

Verification on the final commit:
- Probes (`round_eval_order`, `round_eval_values`, `round_eval_fraction`): both `g`/`d` builds match CPython.
- Refusal probe: `round(ndigits=2)` refused by name with `round() missing required argument number`.
- All 10 `lab/compare` sources: codegen byte-identical to base `dafa966`.
- `test_ail_std_fractions`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: 4/4 pass, 0 failed (442s).
- `update_manifest.py --check`: pass.
[cost $0.0187, opencode tokens {"total": 1260193, "input": 61289, "output": 5459, "reasoning": 4453, "cache.write": 0, "cache.read": 1188992}]
    tool time: bash 14.7 min, edit 0.0 min, write 0.0 min
        443s bash   python3 tools/par_check.py -j 2 test_ail_std_fractions test_ail_safetynet test_ail_files test_ail_corpus_findi
        339s bash   python3 tools/par_check.py -j 2 test_ail_std_fractions test_ail_safetynet test_ail_files test_ail_corpus_findi
         28s bash   args=(); for f in lab/compare/src/*/main.ail; do args+=(--source "$(cat "$f")"); done; python3 tools/codegen_d
         23s bash   for p in /tmp/probes/round_eval_order.py /tmp/probes/round_eval_values.py /tmp/probes/round_eval_fraction.py /
         23s bash   for p in /tmp/probes/round_eval_order.py /tmp/probes/round_eval_values.py /tmp/probes/round_eval_fraction.py; 
         23s bash   for p in /tmp/probes/round_eval_order.py /tmp/probes/round_eval_values.py /tmp/probes/round_eval_fraction.py; 
          0s bash   python3 tools/update_manifest.py 2>&1 | tail -10; python3 tools/update_manifest.py --check 2>&1 | tail -10; gi
          0s bash   python3 tools/update_manifest.py 2>&1 | tail -20 && python3 tools/update_manifest.py --check 2>&1 | tail -20 &

## review 1
[model opencode-go/deepseek-v4.1-flash]
**Change reviewed:** `work..HEAD` adds 12 `fractions` programs in `lab/stdlib/fractions/`, fixes three general-path/prelude bugs (Fraction `/0` message used the wrong denominator; `round()` now accepts `number=`/`ndigits=` and lowers keyword values in source order; tuple-key table `KeyError` keeps the raw key when a bound `KeyError` handler exists), and adds/registers `test_ail_std_fractions`. The latest commit `159be24` is exactly the round evaluation-order fix.

**Probes (`/tmp/rprobes/`, both `g`/`d` builds vs CPython):**
- `r1_order` both keyword orders, mixed positional/keyword, `number=` only — match.
- `r2_vals`, `r7_none` values via arg, list item, attribute, dict value; `ndigits=None` in both orders — match.
- `r4_frac` `Fraction(5,7)/0`, `Fraction(200,1)/0`, `Fraction(0,1)/0`, `Fraction(-3,4)/0` and `/Fraction(0,7)` — match on HEAD; base prints `Fraction(7|4|200, 0)` (the bug this change fixes).
- `r5_keyerr`, `r6_key`, `r8_tables`, `r9_tab`, `r10_tab_int` KeyError with str/int/float/bool/tuple keys via access and pop — match on HEAD; also match on base, so no regression from the raw-key gating.
- `r3_refuse` `round(ndigits=2)` — refused by name `round() missing required argument number` (exit 3), as reported.

**Checks:**
- 10 `lab/compare` sources: old/new codegen SHA-256 identical (all 10) against `work`/`dafa966` — verified.
- `test_ail_std_fractions` 293.6s, `test_ail_safetynet` 202.0s, `test_ail_files` 82.4s, `test_ail_corpus_findings3` 196.9s — all pass, 0 failed on HEAD.
- `tools/update_manifest.py --check` — rc 0.
- All 12 lab programs are 22–48 lines, use arithmetic/construction/keywords/round/limit_denominator/as_integer_ratio/errors/stdin; the test builds each and compares stdout+exit with CPython.
- Report claims: all verified. The diff matches the report; no hidden extra behaviour.

**Pre-existing:** none observed (base-only differences were the intended fixes; no HEAD difference is also present on base).
**Unverified:** runtime instruction counts; the change is compile-time/error-path only, so no hot path was measured.

VERDICT: ACCEPT
[cost $0.0329, opencode tokens {"total": 1557393, "input": 74727, "output": 6754, "reasoning": 22088, "cache.write": 0, "cache.read": 1453824}]
    tool time: bash 12.0 min
        295s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT; date; timeout 900 python3 ../tools/par_check.py -j 2 test_ail_
        198s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT; date; timeout 1200 python3 ../tools/par_check.py -j 2 test_ail
         53s bash   cd /home/runner/work/ail-ci/ail-ci; bash ~/tools/cmp.sh lab/stdlib/fractions/probability.py /tmp/base 2>&1 | t
         46s bash   cd /tmp && mkdir -p pathtest2 && cp /home/runner/work/ail-ci/ail-ci/lab/stdlib/fractions/probability.py pathte
         40s bash   cd /home/runner/work/ail-ci/ail-ci; date; args=(); for f in lab/compare/src/*/main.ail; do args+=(--source "$(
         25s bash   cd /home/runner/work/ail-ci/ail-ci; date; for p in /tmp/rprobes/r1_order.py /tmp/rprobes/r2_vals.py /tmp/rprob
         23s bash   cd /home/runner/work/ail-ci/ail-ci; date; for p in /tmp/rprobes/r4_frac.py /tmp/rprobes/r6_key.py /tmp/rprobes
         16s bash   cd /tmp/rprobes cat > r9_tab.py <<'EOF' def main():     outcomes = {}     for r in range(4):         for b in 

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-01T10:26:46Z
