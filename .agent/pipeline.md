# job job-prog7-11020729  started 2026-11-01T22:45:18Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Done. Commits on `job-prog7-11020729`: `8df3227`, `f496dcb`, `f7f5cdd` (top).

**Result**
- Profiled all 8 programs; hot-function table and reasons in `lab/progfix/prog7.md`.
- Already fully typed: `t018`, `g15_018`, `t474`, `g23_038`.
- Newly typed: `g10_032` (hot `largest_region`).
- Reader/compiler fixes: bool rows are `_AilRow_bool`; `boolkind` resolves `row[i]` to the row class; loops over constant tuple displays are lowered without forcing the tuple pass when that is the program’s only tuple use.
- Follow-ups recorded with exact messages: `g12_034` (`Random.randrange must take plain positional arguments...`), `g14_038` (`'obj' is annotated object...`, `sys.getsizeof ...`), `t184` (`json.loads(s): the type of the result is not declared here...`). `g14_038` still does not build on either AIL path (pre-existing).

**Verification**
- 7/8 programs build and match CPython on the default build; the other is the pre-existing `g14_038` build failure.
- `lab/compare`: all 15 task/build combinations that produced C on both base and HEAD are byte-identical; the other 5 failed on the base too.
- Tests on final commit: `test_ail_prog7`, `test_ail_tuples`, `test_ail_nested_lists`, `test_ail_boolfield`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 7/7 pass. `test_ail_typedreach1/2` also pass.
- Probes `/tmp/probes/p_g10_exact.py`, `p_g10_cases2.py`, `p_tuple_iter.py`, `p_tuple_iter_typed.py`, `p_tuple_value.py`, `p_tuple_names.py`, `p_tuple_empty.py`, `p_tuple_mixed.py`, `p_nested_bool.py`, `p_bool_rows.py`: all match CPython on both `cmp.sh` builds. `manifest --check` passes.
[cost $0.2024, opencode tokens {"total": 31372611, "input": 310875, "output": 47309, "reasoning": 57499, "cache.write": 0, "cache.read": 30956928}]
    tool time: bash 24.5 min, edit 0.0 min, read 0.0 min, write 0.0 min
        328s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_prog7 test_ail_tuples
        265s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_prog7 test_ail_tuples
        206s bash   cd /home/runner/work/_temp/w2 && rm -rf /tmp/prog7/cdiff /tmp/prog7/clogs && mkdir -p /tmp/prog7/cdiff/base /t
        194s bash   cd /home/runner/work/_temp/w2 && mkdir -p /tmp/prog7/cdiff/base /tmp/prog7/cdiff/cur /tmp/prog7/clogs && cat >
         98s bash   cd /home/runner/work/_temp/w2 && rm -rf /tmp/prog7/cdiff/cur && mkdir -p /tmp/prog7/cdiff/cur && rm -f /tmp/pr
         93s bash   cd /home/runner/work/_temp/w2 && python3 tools/update_manifest.py && python3 tools/update_manifest.py --check 
         35s bash   cd /home/runner/work/_temp/w2 && rm -rf /tmp/var_prog7 && cp -a /tmp/base_prog7 /tmp/var_prog7 && cat > /tmp/p
         30s bash   cd /home/runner/work/_temp/w2 && for p in p_g10_exact p_g10_cases2 p_tuple_iter p_tuple_iter_typed p_tuple_val

## review 0
[model opencode-go/deepseek-v4.1-flash]
**What the change really does:** types bool rows as `_AilRow_bool`, resolves `row[i].field` stores to the row class when the list is annotated `list[Row]` or built from `Row(...)` literals, and lowers `for … in (constant tuple display)` to a pre-built annotated list without forcing the tuple pass by itself. This matches the report.

**Probes** (all in `/tmp/rprobes`, run with `cmp.sh` on HEAD; base where noted; `g` = general path, `d` = default):

- `p_bool_row`, `p_bool_mixed_rows`, `p_bool_flat`, `p_bool_row_assign`, `p_bool_row_mut`, `p_bool_eq_int`, `p_bool_row_arg`, `p_bool_to_int_arg`, `p_bool_row_alias`, `p_bool_mixed_in_row`, `p_bool_two_classes`, `p_bool_ann_lie` — g/d match CPython.
- `p_bool_ops` — HEAD g/d match; **base default is wrong** (prints `1/0` for bool rows), so this change fixes it.
- `p_tuple_arith`, `p_tuple_nested_lists`, `p_tuple_alias`, `p_tuple_target`, `p_tuple_break`, `p_tuple_elem_name`, `p_tuple_elem_print`, `p_tuple_nested_loops`, `p_tuple_while`, `p_tuple_ann`, `p_tuple_none`, `p_tuple_gen_yield`, `p_tuple_forced_empty`, `p_tuple_forced_mixed` — g/d match CPython.
- `p_tuple_empty`, `p_tuple_mixed`, `p_tuple_overflow` — same (refusal/general) on base and HEAD.
- `p_const_loop_only`, `p_nofeature` — C byte-identical to base on both builds (`--debug-dir`).
- All 8 task programs: 7 build/match; `g14_038` fails identically on base. Typed status: `t018`, `g15_018`, `t474`, `g23_038`, `g10_032` typed; `g10_032` was general on base; `g12_034`, `t184` general with the reported messages.
- lab/compare: all 15 build combinations that succeed on both base and HEAD are byte-identical (`berth_sim` both builds; 10 `main.ail` default; 5 `main.py`); the rest fail identically on base.

**Pre-existing (not caused):**
- `p_tuple_bool`: typed tuple iteration prints `1/0` for bools instead of `True/False`; identical on base.
- `p_bool_row_arith`: `[False] * 3` in mixed use fails to compile on both base and HEAD.
- `g14_038` build failure; `p_tuple_overflow` int64 constant refusal — identical on base.

**Claims:** hot-function profile percentages — unverified (I checked typed/general status and outputs, not `cProfile` shares). Everything else in the report is verified. The "15 combinations byte-identical" claim is verified.

**Tests:** `test_ail_prog7`, `test_ail_safetynet`, `test_ail_tuples`, `test_ail_nested_lists`, `test_ail_boolfield` all pass; `update_manifest.py --check` passes.

**Unverified:** instruction counts (`perf_event_open` is denied in this container); the worker's own `/tmp/probes` files were not re-run (I used my own); wider suite not run, as instructed.

VERDICT: ACCEPT
[cost $0.0781, opencode tokens {"total": 4054212, "input": 266300, "output": 14130, "reasoning": 30678, "cache.write": 0, "cache.read": 3743104}]
    tool time: bash 19.3 min
        501s bash   cd /home/runner/work/_temp/w2 && rm -rf /tmp/lc && mkdir -p /tmp/lc for t in berth_sim chain_relax echo_pack l
        120s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && nohup python3 ../tools/par_check.py -j 2 test_ail_prog7 test_ail_
        108s bash   cd /home/runner/work/_temp/w2 && rm -rf /tmp/la && mkdir -p /tmp/la for t in berth_sim chain_relax echo_pack l
         90s bash   sleep 90; tail -8 /tmp/extra.log; date
         60s bash   sleep 60; tail -8 /tmp/extra.log; date
         34s bash   cd /home/runner/work/_temp/w2 && for f in lab/census/programs/dev/t018.py lab/census/programs/gdev/g12_034.py 
         30s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && setsid bash -c 'python3 ../tools/par_check.py -j 2 test_ail_safet
         26s bash   cd /home/runner/work/_temp/w2 && for wt in head base; do if [ $wt = base ]; then W=/tmp/base; else W=$PWD; fi;

## full suite
test_ail_fuzz38

## worker report (suite fix)
[model opencode-go/deepseek-v4.1-flash]
Fixed and committed as `1ae715c`.

- Cause: the compiler-injected `_ail_srepr` used a hardcoded, incomplete printability table, so the default and general paths both printed Unicode 15.1 characters raw.
- Fix: `tuplegen.py` now builds `_ail_unprintable` from the running CPython’s `str.isprintable()` table via `cruntime._host_unprintable_rows()`.
- `test_ail_fuzz38` passes; `test_ail_prog7`, `test_ail_tuples`, `test_ail_nested_lists`, `test_ail_boolfield`, and `test_ail_ctime` also pass.
[cost $0.0286, opencode tokens {"total": 2151042, "input": 89454, "output": 6921, "reasoning": 8075, "cache.write": 0, "cache.read": 2046592}]
    tool time: bash 2.3 min
        126s bash   python3 -m unittest -q test_ail_prog7 test_ail_tuples test_ail_nested_lists test_ail_boolfield test_ail_ctime
          4s bash   cd /tmp/fz38 && rm -f exe_g exe_d && AIL_NO_CACHE=1 AIL_QUIET_FALLBACK=1 AIL_UNIFIED_FORCE=1 python3 -B /home/
          4s bash   python3 -m unittest -q test_ail_fuzz38
          2s bash   python3 -m unittest -q test_ail_fuzz38 2>&1 | tail -80
          1s bash   cd /tmp/fz38 && rm -rf dbg exe_g && AIL_NO_CACHE=1 AIL_QUIET_FALLBACK=1 AIL_UNIFIED_FORCE=1 python3 -B /home/r
          1s bash   mkdir -p /tmp/fz38 && cat > /tmp/fz38/p.py <<'EOF' def show(s: str) -> None:     print(repr(s), len(repr(s))) 
          1s bash   cd /tmp/fz38 && rm -f exe_d && AIL_NO_CACHE=1 AIL_QUIET_FALLBACK=1 python3 -B /home/runner/work/_temp/w2/AIL_C
          0s bash   git log --oneline --all -30 && git show 8b1e28a --stat

## full suite again
no new failures

FINAL VERDICT: ACCEPT  2026-11-02T04:08:19Z
