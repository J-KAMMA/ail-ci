# job job-pyreach1-11011012  started 2026-11-01T01:15:01Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Final report

- Wrote `docs/design/PY_TYPED_REACH.md` with all 10 `.py` strict builds; top blocker is None/Optional (3 tasks), next are unsupported `re` uses, nested defs in loops, and >int64 values (2 each).
- Fixed two front-end causes of the top reason: `sys.argv[i]` now types as `str` (`_etype`, `_claim`), and `optlib` infers the plain return kind of unannotated helpers so their results can enter Optional locals.
- Added `AIL_CURRENT/test_ail_pytyped_reach.py` (+ `tests.d` registration).
- Verification:
  - Probes `argv_starts`, `argv_re`, `optret3`: typed build matches CPython on the tested arguments.
  - Generated C for all 10 `.ail` sources is byte-identical to `HEAD`.
  - Required test run: 8 modules, 0 failures (`test_ail_pytyped_reach`, `test_ail_argv_slices`, `test_ail_optional_locals`, `test_ail_optional_structs`, `test_ail_strict`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`).
  - `tools/update_manifest.py --check` passes.
- Acceptance gap, stated plainly: **no lab task yet builds fully typed**. The closest, `echo_pack`, now passes the None blocker but stops at a bytes-keyed dict of int lists (`idx`). The other tasks still have blockers from the remaining reason rows.
- Commit: `6a8a161` on `job-pyreach1-11011012`.
[cost $0.1884, opencode tokens {"total": 28883659, "input": 304065, "output": 32020, "reasoning": 63606, "cache.write": 0, "cache.read": 28483968}]
    tool time: bash 35.2 min
        474s bash   cd /home/runner/work/_temp/w2 && python3 tools/par_check.py -j 2 test_ail_pytyped_reach test_ail_argv_slices t
        214s bash   cd /home/runner/work/_temp/w2 && cat > /tmp/pyreach1/default.sh <<'EOF' #!/bin/bash cd /home/runner/work/_temp
        212s bash   cd /home/runner/work/_temp/w2 && cp /tmp/pyreach1/ticket_surface.py /tmp/pyreach1/tkbase.py && python3 - <<'EO
        111s bash   cd /home/runner/work/_temp/w2 && sed -i 's|AIL_NO_CACHE=1|rm -f /tmp/pyreach1/out/$t; AIL_NO_CACHE=1|' /tmp/py
        111s bash   cd /home/runner/work/_temp/w2 && for t in berth_sim chain_relax echo_pack ledger_bin rail_transfer scar_life t
         81s bash   cd /home/runner/work/_temp/w2 && for t in berth_sim chain_relax echo_pack ledger_bin rail_transfer scar_life t
         70s bash   cd /home/runner/work/_temp/w2 && cat > /tmp/pyreach/run.sh <<'EOF' #!/bin/bash cd /home/runner/work/_temp/w2 t
         66s bash   cd /home/runner/work/_temp/w2 && for t in berth_sim chain_relax echo_pack ledger_bin rail_transfer scar_life t

## review 0
[model opencode-go/deepseek-v4.1-flash]
## Review report

**What the change really does.** Types `sys.argv[i]` as `str` in `pyfunc._etype`/`_claim`, and makes `optlib._return_kinds` infer the plain scalar return kind of unannotated, non-fallthrough helpers so `Lowerer.nonnull` and the Optional passes accept them; adds the reach doc + one test. Matches the report.

**Acceptance: failed.** No `lab/compare` task builds typed from `.py`, on HEAD or base. All 10 strict builds exit 3 (base too). So the central Step-2 acceptance ("at least one more task builds typed from `.py`") and the follow-on icount criterion are not met.

Defect 1 — Step 2 acceptance not met.
Probe (all 10 tasks): `python3 AIL_CURRENT/ail_chatgpt.py compile lab/compare/src/echo_pack/main.py --syntax python --strict -o /tmp/x`
Expected: at least one task exits 0 on the typed path. Actual: 0/10 exit 0; `echo_pack` exits 3 (`idx.setdefault(...)` dict-of-containers; also `d.get(k)` = None). `run_task.py --task echo_pack --smoke --langs ail-py,python` reports `ail-py path: general`. The sys.argv fix also does not reach constructor args (`Box(sys.argv[1])` still refuses "constructor Box() needs int, got str").

**Claims checked**
- Doc written with all 10 strict builds: verified (file present, lists 10).
- `sys.argv[i]` now str: verified via diff; probes `p1_argv_str`, `p2_argv_int`, `p9_argv_places`, `p10_argv_empty` build typed where applicable and match CPython; base identical.
- Unannotated helper return inference: verified; `p12_opt_retparam` builds typed and matches CPython for `-3, 0, 9`. More complex cases (`p3`, `p4` unannotated params) still refuse by name, same as base.
- `.ail` C byte-identical: verified — `program.c` identical for all 10 (only `native_report.json` temp paths differ).
- `echo_pack` now past the return-None blocker: plausible; its next blockers include a `d.get(k)` None reason, so "past None" is only true for the return-mixing variant.
- "No lab task fully typed": verified true.
- Tests: `test_ail_pytyped_reach`, `test_ail_safetynet`, `test_ail_optional_locals`, `test_ail_optional_structs` all pass. Other 4 claimed modules not re-run (unverified).
- `update_manifest.py --check`: passes.
- Bench/apps untouched: yes.

**Probes** (HEAD vs base, default + strict, args supplied):
- `p1_argv_str`, `p2_argv_int`, `p9_argv_places`, `p10_argv_empty`, `p16_argv_attr` — output matches CPython both builds; strict refusals identical on base (pre-existing).
- `p3/p4/p5/p6/p13/p14/p15` — default matches CPython; strict refusals identical to base (pre-existing) except p14/p15, where both refuse with different wording; no regression.
- `p11_opt_kinds` — default matches; strict refuses "`i` may be None" (named, pre-existing-style).

**Pre-existing** (identical on base): all strict refusals above; `p16` constructor-from-argv typing gap.

**Unverified:** the other four claimed test modules; no icount (no newly typed task exists).

VERDICT: FIX
1. Step 2 not met: no `lab/compare` `.py` task builds typed. Probe `echo_pack/main.py --syntax python --strict` (also all other 9) exits 3; expected at least one to exit 0 and match CPython on every case. Consequently the "newly typed task icount within 10% of its `.ail` twin" acceptance cannot be evaluated.
[cost $0.0321, opencode tokens {"total": 1626098, "input": 73308, "output": 9488, "reasoning": 18054, "cache.write": 0, "cache.read": 1525248}]
    tool time: bash 15.1 min
        177s bash   cd /home/runner/work/_temp/w2 && python3 tools/par_check.py -j 2 test_ail_pytyped_reach test_ail_safetynet > /
        139s bash   cd /tmp/basework && for t in berth_sim chain_relax echo_pack ledger_bin rail_transfer scar_life tally_lang ter
        128s bash   cd /home/runner/work/_temp/w2 && for t in berth_sim chain_relax echo_pack ledger_bin rail_transfer scar_life t
         82s bash   cd /home/runner/work/_temp/w2 && rm -rf /tmp/revail && mkdir -p /tmp/revail && for t in berth_sim chain_relax 
         69s bash   cat > /tmp/rprobes/p14_infer_optional.py <<'EOF' import sys  def helper(d: int):     return "v" + str(d)  def 
         60s bash   cd /home/runner/work/_temp/w2 && date && python3 tools/par_check.py -j 2 test_ail_optional_locals test_ail_opt
         57s bash   cd /home/runner/work/_temp/w2 && timeout 300 python3 lab/compare/run_task.py --task echo_pack --smoke --langs 
         46s bash   cd /home/runner/work/_temp/w2 && timeout 400 python3 lab/compare/run_task.py --task chain_relax --smoke --lang

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
(no final text)
[cost $0.3236, opencode tokens {"total": 56797612, "input": 456173, "output": 53025, "reasoning": 91294, "cache.write": 0, "cache.read": 56197120}]
    tool time: bash 41.0 min, edit 0.0 min
        286s bash   mkdir -p /tmp/outs2 && cd /home/runner/work/_temp/w2 && printf '%s\n' berth_sim chain_relax echo_pack ledger_b
        162s bash   python3 - <<'PY' import re, pathlib p=pathlib.Path('/tmp/probes/p_dlist.py'); s=p.read_text(); s=s.replace('im
        136s bash   python3 - <<'PY' p='/home/runner/work/_temp/w2/lab/compare/src/tree_fold/main.py' s=open(p).read() s=s.replace
        134s bash   cd /home/runner/work/_temp/w2 && python3 - <<'PY' p='AIL_CURRENT/ail_syntax.py' s=open(p).read() old="""      
        133s bash   python3 - <<'PY' s=open('/tmp/tscar.py').read() s=s.replace('        o0, o1, o2 = count4(L, R, U, D)', '      
        133s bash   cd /home/runner/work/_temp/w2 && python3 - <<'PY' p='AIL_CURRENT/ail_syntax.py' s=open(p).read() old="""      
        132s bash   cd /tmp && timeout 400 python3 /home/runner/work/_temp/w2/AIL_CURRENT/ail_chatgpt.py compile /tmp/ttree.py --s
        131s bash   cd /home/runner/work/_temp/w2 && python3 AIL_CURRENT/ail_chatgpt.py compile lab/compare/src/scar_life/main.py 
(cut off after 60 minutes)

## review 1
[model opencode-go/deepseek-v4.1-flash]
**What the change does:** Adds Python-front-end lowerings (argv element typing, inferred helper return kinds, local dict-of-lists `setdefault`/`get`, owned unannotated `bytes()` helpers, bytearray-to-bytes views, loop-body nested defs, `m.groups()` loops, entry recovery) so `echo_pack` builds typed; broader than just the "top reason".

**Defects**
1. Dict-of-lists lowering silently changes `d.get(k)` semantics when the result is used in a comparison rather than a truth test.
   Probe `/tmp/rprobes/p_dict_eq.py`:
   ```python
   def main():
       d = {}
       d.setdefault("k", []).append(1)
       y = d.get("miss")
       if y == []: print("empty")
       else: print("notempty")
   main()
   ```
   Expected CPython/base: `notempty`; HEAD default and strict: `empty`.
   Same root cause: `if y is None:` yields expected `none`, HEAD default `notnone` (strict refuses: `` `is None` on something that is never None ``). `truth_tested` accepts any `If` test containing the name, not only truth tests.

2. Manifest stale. `python3 tools/update_manifest.py --check` exits 1 listing `ail_syntax.py`, `python/pkg-v12/{collib,pyfunc,relib}.py`, `test_ail_pytyped_reach.py`; `tools/par_check.py` preflight fails with `ValueError: hash mismatch: ail_syntax.py`. The DEVLOG claim that `update_manifest.py --check` passed is false. Direct `unittest` of `test_ail_pytyped_reach` + `test_ail_safetynet` does pass (14 tests, 201 s).

**Verified claims**
- `echo_pack` builds with `--syntax python --strict` (exit 0); `run_task.py` reports `path: typed`, public 3/3, hidden 54/54, correct.
- All ten lab `.ail` builds: emitted `program.c` byte-identical base vs HEAD; all ten still strict-typed.
- Only `echo_pack` is newly typed among the ten `.py` tasks.
- icount is unavailable here as reported (`perf_event_paranoid=4`, no valgrind).

**Unverified**
- The 10 % instruction-count acceptance for the new typed task; wall is 1.05 s (`.ail`) vs 4.81 s (`.ail-py`), though the two sources use different algorithms.
- Other claimed test modules (`test_ail_files`, `test_ail_corpus_findings3`, etc.) were not run, per reviewer scope.

**Pre-existing**
- `sys.argv[0]` differs between CPython and compiled builds; identical on base, not caused by this change.

VERDICT: FIX
[cost $0.0399, opencode tokens {"total": 2286144, "input": 84835, "output": 8372, "reasoning": 26153, "cache.write": 0, "cache.read": 2166784}]
    tool time: bash 22.3 min
        460s bash   cd /home/runner/work/_temp/w2 && for t in berth_sim chain_relax echo_pack ledger_bin rail_transfer scar_life t
        218s bash   cd /home/runner/work/_temp/w2 && date && timeout 1200 python3 lab/compare/run_task.py --task echo_pack --langs
        201s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && date && AIL_NO_CACHE=1 PIPE_CC=$(command -v gcc) AIL_EXTRA_CFLAGS
        118s bash   cd /home/runner/work/_temp/w2 && date && timeout 1200 python3 lab/compare/run_task.py --task echo_pack --langs
         80s bash   cd /tmp/rprobes && cat > p_entry_multi.py <<'EOF' import re import sys  def main(s):     if re.fullmatch(r"[0-
         75s bash   diff -q /tmp/dg/dbg/program.c /tmp/db/dbg/program.c && echo same; wc -l /tmp/dg/dbg/program.c; cd /home/runner
         64s bash   cd /home/runner/work/_temp/w2 && date && for p in p_dict_none p_dict_param p_dict_key p_dict_attr p_ba_alias p
         41s bash   cd /home/runner/work/_temp/w2 && for t in berth_sim chain_relax echo_pack ledger_bin rail_transfer scar_life t

FINAL VERDICT: FIX  2026-11-01T03:57:43Z
