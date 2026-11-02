# job job-prog23-11021945  started 2026-11-02T10:49:53Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the review defect.

- `set(...)` with str/bytes keys now refuses the typed fill, and an int set-operator result cannot rebind a str/bytes-keyed destination. The function falls back to the general path; `--strict` reports the named blocker.
- Probes (all match CPython on both builds): rebind via `& | - ^`, branch bindings, tuple/list/name sources, bytes sets, loop rebind, reverse bind order, aliases, and values through an argument, list item, attribute and dict value.
- Tests pass: `test_ail_prog23`, `test_ail_sets_general`, `test_ail_tuples`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 6 modules, 475 s, 0 failed.
- `tools/update_manifest.py` + `--check` pass.
- The ten `lab/compare/src/*/main.ail` generated C files are byte-identical to pre-fix HEAD (`AIL_IR=0`).

Committed as `6c4d709`.
[cost $0.0000, opencode tokens {"total": 5007066, "input": 352209, "output": 12694, "reasoning": 15987, "cache.write": 0, "cache.read": 4626176}]
    tool time: bash 10.3 min
        476s bash   python3 tools/par_check.py -j 2 test_ail_prog23 test_ail_sets_general test_ail_tuples test_ail_safetynet test_
         48s bash   mkdir -p /tmp/probes cat > /tmp/probes/setrebind_literal_tuple.py <<'EOF' def run() -> None:     c = set(("x",
         41s bash   rm -rf /tmp/cmpc_before /tmp/cmpc_after && mkdir -p /tmp/cmpc_before /tmp/cmpc_after run_side() { wt=$1; out=$
         18s bash   for p in rebind_strset_to_intset_op strset_print_then_intalias strset_then_intop_noprint strset_then_intset_no
         11s bash   cat > /tmp/probes/setstr_via_argument.py <<'EOF' def build(words: list[str]) -> None:     c = set(words)     a
          5s bash   cat > /tmp/probes/strset_print_then_intalias.py <<'EOF' def run() -> None:     c = set(["x", "y"])     print(s
          3s bash   cat > /tmp/probes/setstr_via_attribute.py <<'EOF' class Holder:     def __init__(self) -> None:         self.w
          3s bash   cat > /tmp/probes/strset_and_intset.py <<'EOF' def run() -> None:     c = set(["x", "y"])     print(sorted(c))

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review report

**What the change does.** It adds two named refusals in `pyfunc.py`: (1) an unannotated `set(...)` whose keys are str/bytes is kept off the typed path (annotated `set[str]` still compiles typed), and (2) an int set-operator assignment (`& | - ^`) refuses a destination already bound to a str/bytes-keyed set. Both make the function take the general path; `--strict` names the blocker. `test_ail_prog23.py` gains a regression test; manifest hashes and DEVLOG/prog23 notes are updated. This matches the report.

**Probes** (HEAD `/home/runner/work/ail-ci/ail-ci`, base `/tmp/base` at `work`; all via `~/tools/cmp.sh`, both builds):
- Exact review probe: `['x','y']` then `[2]` on general and default build — fixed (base default also fails on the first str set).
- All four operators, branch binding, tuple/list/name sources, bytes sets, `set()`+`.add(str)`, annotated `set[str]` (still typed), rebind both orders, aliases, arg/list-item/attribute/dict-value sources: all match CPython.
- Regular int set ops and a non-feature program: outputs match; `program.c` byte-identical HEAD vs base.
- All ten `lab/compare/src/*/main.ail` `program.c` files byte-identical to base (verified by `--debug-dir`).

**Pre-existing (identical on base, not caused by the change):** str-keyed sets built from a list comprehension or nested inline in `print(...)`/`sorted(...)` still fail the default build with the same `ail_tab_put ... ail_str` gcc error; several other typed-set forms remain refused on base.

**Tests.** `test_ail_prog23` 34.7s and `test_ail_safetynet` 167.8s pass on HEAD; `update_manifest.py --check` passes.

**Claim check.** Refusals/fallbacks: verified. Probes match CPython: verified for the cases above. Six-module test run: only the two required modules re-run here (passed); the other four unverified. Manifest: verified. Ten byte-identical C files: verified. Minor wording issue: “only programs that previously were refused” is inexact — plain str `set(...)` previously compiled-failed rather than being refused, but it was already broken.

**Unverified.** Instruction counts/speed (`perf_event_open` unavailable; the change adds only compile-time checks, no runtime path) and the four non-required test modules.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1246354, "input": 51512, "output": 7908, "reasoning": 15350, "cache.write": 0, "cache.read": 1171584}]
    tool time: bash 7.6 min
        169s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 600 python3 ../tools/par_check.py -j 2 test_
        120s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && nohup python3 ../tools/par_check.py -j 2 test_ail_prog23 tes
         84s bash   cd /tmp && rm -rf /tmp/lch /tmp/lcb && mkdir -p /tmp/lch /tmp/lcb for d in /home/runner/work/ail-ci/ail-ci/lab
         24s bash   cd /home/runner/work/ail-ci/ail-ci && mkdir -p /tmp/rprobes/head && ls /tmp/rprobes/*.py | xargs -P2 -I{} bash
         15s bash   cd /tmp/rprobes cat > p_mixed_setop.py <<'EOF' def run() -> None:     a = set(["x", "y"])     b = set([1, 2]) 
         11s bash   cd /home/runner/work/ail-ci/ail-ci && for n in p_strset_param_op p_annot_strset_op p_intop_then_strset p_strsp
         10s bash   cd /tmp/rprobes && cat > p_strset_inprint.py <<'EOF' def run() -> None:     print(sorted(set(["x", "y"]))) run
          9s bash   cd /tmp/rprobes && cat > p_annot_strset_plain.py <<'EOF' def run() -> None:     c: set[str] = set(["x", "y"]) 

## full suite
test_ail_libc_names

## worker report (suite fix)
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed as `5c53266`.

- Root cause: `_etype` evaluated both operands of every `BinOp` twice (ref-kind check + result), making long nested numeric chains exponential; `test_ail_libc_names` timed out compiling one.
- Fix: evaluate each operand kind once and reuse it. Manifest pin updated.
- Verified: `test_ail_libc_names` (6.5s), `test_ail_prog23`, `test_ail_builtin_shadowing`, `test_ail_int_base` all pass; `update_manifest.py --check` passes.
[cost $0.0000, opencode tokens {"total": 2156718, "input": 160140, "output": 6038, "reasoning": 8204, "cache.write": 0, "cache.read": 1982336}]
    tool time: bash 27.2 min
        600s bash   cd AIL_CURRENT && python3 - <<'EOF' import test_ail_libc_names as t s,e=t.program() open('/tmp/libc_names.ail'
        200s bash   cd AIL_CURRENT && time timeout 200 python3 -X utf8 -B ail_chatgpt.py compile /tmp/libc_names.ail -o /tmp/libc_
        181s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_libc_names 2>&1 | tail -80
        120s bash   ls /tmp/base 2>/dev/null | head; ls /tmp | head -50; kill 94492 2>/dev/null; pkill -f 'ailc-47fsol7u' 2>/dev/n
        120s bash   pkill -f 'pyc.py --file /tmp/ailc-' ; pkill -f 'ail_chatgpt.py compile /tmp/libc_names' ; sleep 1; ps -ef | gr
        120s bash   cd /tmp/base/AIL_CURRENT && time timeout 120 python3 -X utf8 -B ail_chatgpt.py compile /tmp/libc_names.ail -o 
         94s bash   cd AIL_CURRENT && for n in 1 2 5 10 20 30 44; do python3 - "$n" <<'EOF' import sys n=int(sys.argv[1]) import t
         60s bash   cd AIL_CURRENT && python3 - <<'EOF' import test_ail_libc_names as t for n in (10,12,15,20):     names=t.NAMES[

## full suite again
no new failures

FINAL VERDICT: ACCEPT  2026-11-02T14:17:14Z
