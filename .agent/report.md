# job job-pyreach1-11020650  started 2026-11-01T21:51:04Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed both review defects and committed as `9ba42f3`.

- **Semantics:** `lower_dict_of_lists` now accepts a `get` result only in truth-only positions (`if x:`, `while x:`, `and`/`or`, `not x`). Comparisons like `x == []` / `x is None` leave the source untouched: default build matches CPython, `--strict` refuses by name. `echo_pack` still builds typed.
- **Manifest:** refreshed pins; `update_manifest.py --check` and `ail_check.preflight` both exit 0.
- **Probes (both builds):** `p_dict_eq`, `p_dict_none`, `p_dict_truth`, `p_dict_not`, `p_dict_and`, `p_dict_default`, `p_dict_keyforms`, `p_dict_types`, `p_dict_while` — all match CPython; the first two are refused by name under `--strict` (exit 3).
- **Tests:** `test_ail_pytyped_reach` 26.9s, `test_ail_files` 99.2s, `test_ail_safetynet` 166.6s, `test_ail_corpus_findings3` 240.7s — 4/4 pass.
- **echo_pack:** `path: typed`, public 3/3, hidden 54/54; ail-py wall 3966 ms vs ail 1059 ms (icount unavailable here).
[cost $0.0000, opencode tokens {"total": 1250935, "input": 27060, "output": 7297, "reasoning": 8898, "cache.write": 0, "cache.read": 1207680}]
    tool time: bash 15.9 min, edit 0.0 min
        368s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_pytyped_reach test_ail_safetyne
        300s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py 2>&1 | tail -20; echo "exit=${PIPESTATUS[0]}"
        220s bash   cd /home/runner/work/ail-ci/ail-ci && python3 lab/compare/run_task.py --task echo_pack --langs ail,ail-py,pyth
         25s bash   cd /tmp/probes && cat > p_dict_keyforms.py <<'EOF' class Box:     def __init__(self):         self.key = "a"  
         18s bash   mkdir -p /tmp/probes && cd /tmp/probes && cat > p_dict_eq.py <<'EOF' def main():     d = {}     d.setdefault("
         16s bash   cd /tmp/probes && for p in p_dict_eq p_dict_none p_dict_truth p_dict_not p_dict_and p_dict_default; do echo "=
          2s bash   cd /home/runner/work/ail-ci/ail-ci && AIL_NO_CACHE=1 python3 AIL_CURRENT/ail_chatgpt.py compile lab/compare/sr
          1s bash   cd /tmp/probes && for p in p_dict_eq p_dict_none; do echo "=== $p strict"; AIL_NO_CACHE=1 python3 /home/runner

## review 0
[model opencode/deepseek-v4.1-flash-free]
## review 2

**What the change does:** `lower_dict_of_lists` now treats a `d.get()` result as lowerable only when every read is a truth-only position (`if x:`, `while x:`, `and`/`or`, `not x`) or sits in the body of a test that guarantees `x` truthy; comparisons (`== []`, `is None`, etc.) are no longer treated as truth tests, so such sources are left unlowered (default matches CPython, `--strict` refuses by name).

**Defects:** none new. The review's two defects are fixed:
- `p_dict_eq.py` / `p_dict_none.py`: base printed `empty`/`notnone`; HEAD prints CPython's `notempty`/`none` on both general and default builds, and `--strict` refuses both by name (exit 3).
- Manifest: `update_manifest.py --check` exit 0; `ail_check.preflight` returns clean.

**Verified claims**
- `echo_pack`: `path: typed`, public 3/3, hidden 54/54; ail-py wall 4055.7 ms vs ail 1061.7 ms (matches report).
- All ten `lab/compare/src/*/main.ail` build with `program.c` byte-identical HEAD vs base.
- Probes on HEAD (general + default) all match CPython: `p_dict_eq`, `p_dict_none`, `p_dict_truth`, `p_dict_bool`, `p_dict_while`, `p_dict_cmpvar`, `p_dict_guard`, `p_dict_keyforms`, `p_dict_types`, `p_dict_orelse`, `p_dict_whilecmp`, `p_dict_alias`. `p_dict_truth` still builds typed under `--strict`.
- `test_ail_pytyped_reach` 26.6 s and `test_ail_safetynet` 162.4 s pass (`par_check -j 2`, 0 failed).

**Pre-existing (not caused by this change, identical on base)**
- Top-level nested def closing over the get result: `p_dict_nesteddef.py` (`def f(): if y == []: ...` inside `main`) prints `empty` vs CPython `notempty` on both HEAD and base; the base's `truth_tested` already ignored top-level nested defs.

**Unverified**
- Instruction-count acceptance: `icount` unavailable on this runner (as reported).
- `p_dict_default` was not run by name (the equivalent 1/2-arg `get` paths were covered).
- `test_ail_files` / `test_ail_corpus_findings3` not re-run (reviewer scope; report claims pass).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 953246, "input": 20979, "output": 5524, "reasoning": 16791, "cache.write": 0, "cache.read": 909952}]
    tool time: bash 8.9 min
        223s bash   cd /home/runner/work/ail-ci/ail-ci && date && timeout 1200 python3 lab/compare/run_task.py --task echo_pack --
        163s bash   cd /home/runner/work/ail-ci/ail-ci && date && timeout 1500 python3 tools/par_check.py -j 2 test_ail_pytyped_re
         72s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/gh /tmp/gb && mkdir -p /tmp/gh /tmp/gb && for t in berth_sim
         21s bash   cd /tmp/rprobes && date && for p in p_dict_eq p_dict_none p_dict_truth p_dict_bool p_dict_while p_dict_nestedd
         19s bash   cd /tmp/rprobes && date && for p in p_dict_eq p_dict_none p_dict_truth p_dict_bool p_dict_while p_dict_nestedd
         14s bash   cd /tmp/rprobes && date && for p in p_dict_cmpvar p_dict_guard p_dict_keyforms p_dict_types; do echo "===== $p
          8s bash   cd /tmp/rprobes && cat > p_dict_alias.py <<'EOF' def main():     d = {}     d.setdefault("k", []).append(1)   
          6s bash   cd /tmp/rprobes && date && for p in p_dict_orelse p_dict_whilecmp; do echo "===== $p HEAD"; bash ~/tools/cmp.s

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-01T23:38:04Z
