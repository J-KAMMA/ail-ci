# job job-onelangs2-11030858  started 2026-11-02T23:58:32Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the remaining defect.

- `AIL_CURRENT/ail_syntax.py`: a second top-level `from ail import X as Y` with a different source name now raises `ail import alias Y is rebound` instead of silently overwriting the alias map. Repeating the same source under the same alias remains allowed.
- Added coverage in `test_ail_ail2py.py` for both the differing-source refusal and the same-source repeat.
- Probe `alias_rebind_same_import.py`: CPython prints `3`/`12`; default and unified builds now refuse by name (previously `2`/`12`).
- `test_ail_ail2py`, `test_ail_python_syntax`, `test_ail_files`, `test_ail_corpus_findings3`: pass. `test_ail_safetynet`: 5/5 pass without the 1.5 GB `ulimit`; under that limit the unrelated `S4_generators_gc` case hits memory pressure.
- `tools/update_manifest.py --check` exits 0; committed as `0d04540`.
[cost $0.0000, opencode tokens {"total": 965745, "input": 63212, "output": 4799, "reasoning": 5574, "cache.write": 0, "cache.read": 892160}]
    tool time: bash 12.2 min, edit 0.0 min
        359s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000 && PYTHONPATH=$PWD/AIL_CURRENT timeout 1500 python3 to
        177s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && PYTHONPATH=$PWD timeout 900 python3 -B test_ail_safetynet.py
        124s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && ulimit -v 1500000 && PYTHONPATH=$PWD timeout 900 python3 -B 
         57s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && PYTHONPATH=$PWD timeout 900 python3 -B - <<'EOF' 2>&1 | tail
          9s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000 && PYTHONPATH=$PWD/AIL_CURRENT timeout 1500 python3 -B
          5s bash   cd /home/runner/work/ail-ci/ail-ci && export PYTHONPATH=$PWD/AIL_CURRENT && for p in /tmp/probes/alias_*.py; d
          1s bash   mkdir -p /tmp/probes && cd /tmp/probes && cat > alias_rebind_same_import.py <<'EOF' from ail import wrapping_a
          1s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review 4

**Diff summary.** 0d04540 adds one guard in `_ail_imports` (`AIL_CURRENT/ail_syntax.py:4134`) refusing a repeated `from ail import X as Y` when `Y` is already mapped to a different source, plus tests/DEVLOG/manifest updates. It does not fully implement the report's broad claim.

**Verified claims**
- `alias_rebind_same_import.py`: HEAD (both builds) refuses `ail import alias w is rebound`; base prints `2`/`12`. Named defect fixed.
- `alias_repeat_same.py` (same source, same alias): matches CPython and its `program.c` is byte-identical to the bare program.
- `alias_three.py`, `alias_second_diffname.py`: match CPython in both builds.
- `no_feature.py` and accepted alias programs: `program.c` identical between `/tmp/base` (work) and HEAD.
- `test_ail_ail2py`, `test_ail_safetynet`: 2/2 pass with `par_check.py -j 2`; `update_manifest.py --check` exits 0.

**Report claim marked false.** "A second top-level `from ail import X as Y` with a different source name now raises" is not true when the first import spells `as Y` with `Y == X`; that first binding is never recorded in `from_aliases`, so the second silently overwrites it.

**Defect**
1. `from ail import wrapping_add as wrapping_add` followed by `from ail import wrapping_mul as wrapping_add` is not refused; earlier loads are rewritten to the later target.
   ```python
   from ail import wrapping_add as wrapping_add
   print(wrapping_add(1, 2))
   from ail import wrapping_mul as wrapping_add
   print(wrapping_add(3, 4))
   ```
   Expected (CPython): `3`, `12`. Actual (HEAD, default and unified): `2`, `12`, exit 0. Cause: the guard only records/checks `alias.asname` when `asname != alias.name`, so the `Y == X` binding is invisible to both the new check and the existing rebound scan. (This silent output also exists at `work`, but it is the same alias-rebinding defect the task asked to close, and it contradicts the report's claim.)

**Pre-existing**
- `from ail import wrapping_add` then `from ail import wrapping_mul as wrapping_add`: refused by name on base and HEAD (valid program, but a named refusal).
- Alias passed as a first-class value (`alias_dictlist.py`): compile refusal `not in the subset: name 'wrapping_add' is not defined` on base and HEAD.
- Assignment rebinding of a plain imported name remains silently accepted on base and HEAD.

**Unverified:** wider suite/CI shards, TCP/current_dir/monotonic values, speed (frontend-only change; no codegen path touched).

VERDICT: FIX
1. `alias_asname_eq_name.py` (above): expected `3`/`12`, actual `2`/`12` in both builds. Record/check every top-level `from ail` alias, including `asname == name`, so a later different-source rebinding is refused.
[cost $0.0000, opencode tokens {"total": 354510, "input": 20525, "output": 3159, "reasoning": 10058, "cache.write": 0, "cache.read": 320768}]
    tool time: bash 3.7 min
        179s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_ail_ail
         13s bash   cd /tmp/base && export PYTHONPATH=$PWD/AIL_CURRENT && for p in /tmp/rprobes/*.py; do echo "===== $(basename $p
         12s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/*.py; do echo "===== $(basename $p) ====="; timeou
         11s bash   cd /home/runner/work/ail-ci/ail-ci && export PYTHONPATH=$PWD/AIL_CURRENT && for p in /tmp/rprobes/*.py; do ech
          5s bash   cd /home/runner/work/ail-ci/ail-ci && export PYTHONPATH=$PWD/AIL_CURRENT && for p in no_feature alias_repeat_s
          1s bash   cd /home/runner/work/ail-ci/ail-ci && export PYTHONPATH=$PWD/AIL_CURRENT && timeout 300 bash ~/tools/cmp.sh /t
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git worktree add /tmp/base work 2>&1 | tail -2; mkdir -p /tmp/rprobes; d
          0s bash   cd /home/runner/work/ail-ci/ail-ci && export PYTHONPATH=$PWD/AIL_CURRENT && for src in 'from ail import wrappi

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed review-5 defect and committed as `cc5e03d`.

- `_ail_imports` now records every top-level `from ail` binding, including `asname == name`; a later different-source rebinding is refused by name (`ail import alias ... is rebound`), and plain imports also refuse later stores instead of silently changing meaning.
- Probes: `alias_asname_eq_name`, `alias_rebind_same_import`, `alias_plain_then_alias_diff` refuse by name in both builds; `alias_repeat_same`, `alias_repeat_same_eq`, `alias_valid` match CPython in both builds.
- All ten converters print `identical`; `ail2py_cpython_check.py`: nine tasks `mismatches 0`, `tally_lang` only `hidden/long_unary_chain`.
- Tests on final commit: `test_ail_ail2py`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_python_syntax`, `test_ail_heapq_bisect`, `test_ail_overflow_error` all pass; `test_ail_safetynet` passes (run without `ulimit -v 1500000`; under that limit its heavy S4 case fails on allocation, independent of this change).
- `tools/update_manifest.py --check` exits 0. Not pushed, per job rules.
[cost $0.0000, opencode tokens {"total": 1088349, "input": 61911, "output": 4693, "reasoning": 6705, "cache.write": 0, "cache.read": 1015040}]
    tool time: bash 22.3 min
        263s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && ulimit -v 1500000 && timeout 1500 python3 ../tools/par_check
        235s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && ulimit -v 1500000 && timeout 1500 python3 ../tools/par_check
        177s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 test_ail_safetynet.py 2>&1 | tail -8
        175s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 test_ail_safetynet.py 2>&1 | tail -6 && 
        158s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 -m unittest test_ail_safetynet.GeneralPa
        121s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && ulimit -v 1500000 && timeout 900 python3 test_ail_safetynet.
        100s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000 && PYTHONPATH=$PWD/AIL_CURRENT timeout 1500 python3 -B
         95s bash   cd /home/runner/work/ail-ci/ail-ci && for t in berth_sim chain_relax echo_pack ledger_bin rail_transfer scar_l

## review 1
[model opencode/deepseek-v4.1-flash-free]
## Review 6

**Diff summary.** `_ail_imports` now records every top-level `from ail` binding in `from_aliases` (plain names included, not only `as` aliases), refuses a bound name already mapped to a different source (`ail import alias Y is rebound`), and exempts all dropped top-level `from ail` nodes from the later-rebinding scan. This matches the worker report.

**Review-5 defect (fixed).** `alias_rebind_same_import.py` (the review's probe): HEAD refuses by name in both builds (`p.ail:3:1: ail import alias w is rebound`); base silently prints `2`/`12` vs CPython `3`/`12`. No longer a silent difference.

**Probes run (HEAD, general + default; compared with base where relevant)**
- `alias_asname_eq_name`, `alias_plain_then_alias_diff`, `alias_plain_then_store`: named refusal, both builds.
- `alias_repeat_same`, `alias_repeat_same_eq`, `alias_single_eq`, `alias_diff_names_same_src`, `alias_plain_then_plain_same`, `alias_valid`: match CPython; same-name/plain-import C is byte-identical to the bare program.
- `no_feature.py`: matches CPython; `--debug-dir/program.c` byte-identical HEAD vs base.
- `import_then_from_alias`, `alias_then_plain_target`, `nested_second_alias`: named refusal on both HEAD and base (no difference).

**Claims:** all verified. Tests on HEAD: `test_ail_ail2py`, `test_ail_python_syntax` pass; `test_ail_safetynet` 5/5 OK; `test_ail_files`, `test_ail_heapq_bisect`, `test_ail_overflow_error`, `test_ail_corpus_findings3` pass. `update_manifest.py --check` rc 0. All ten converters `--check --strict` print `identical`. `ail2py_cpython_check`: nine tasks `mismatches 0`, `tally_lang` only `hidden/long_unary_chain`. Minor wording nuance: base already matched CPython for a loop variable shadowing a plain import; HEAD now refuses that by name (conservative, acceptable).

**Pre-existing** (identical on base): a built-in used as a first-class value (`[w]`, `{'f': w}`, `call(w)`) fails with `name 'wrapping_add' is not defined`; `import ail as w` + `from ail import X as w` and nested/different-source alias confusions are refused on both.

**Unverified:** speed (frontend-only, no codegen/runtime hot path), TCP and heap equal-key details (untouched by this change).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 599364, "input": 24610, "output": 3934, "reasoning": 16196, "cache.write": 0, "cache.read": 554624}]
    tool time: bash 10.8 min
        230s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && ulimit -v 1500000 && timeout 1500 python3 ../tools/par_check
        176s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 -m unittest -q test_ail_safetynet 2>&1 |
         95s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000 && PYTHONPATH=$PWD/AIL_CURRENT timeout 1200 python3 -B
         95s bash   cd /home/runner/work/ail-ci/ail-ci; date; python3 tools/update_manifest.py --check; echo "manifest rc=$?"; exp
         27s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && ulimit -v 1500000 && timeout 1200 python3 ../tools/par_check
          9s bash   cd /home/runner/work/ail-ci/ail-ci; export PYTHONPATH=$PWD/AIL_CURRENT; date; for p in /tmp/rprobes/r6/*.py; d
          6s bash   cd /tmp/rprobes/r6; cat > alias_repeat_same_eq.py <<'EOF' from ail import wrapping_add as wrapping_add print(w
          4s bash   cd /home/runner/work/ail-ci/ail-ci; export PYTHONPATH=$PWD/AIL_CURRENT; date; for p in /tmp/rprobes/r6/alias_t

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-03T02:13:13Z
