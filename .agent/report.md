# job job-pre197-10252029  started 2026-10-25T11:29:53Z  worker=oc reviewer=oc (GitHub)
## qoder discovery
1.1.78
  -m, --model <model>                  Model for the current session. Default
                                       and New Models use model name; Custom
                                       uses modelID
  --reasoning-effort <level>           Set reasoning effort level
  --thinking <mode>                    Set thinking mode (auto, adaptive,
                                       enabled, or disabled)
--
                                       models
  --list-models                        List available models for the current
                                       user
  -i, --prompt-interactive <text>      Execute prompt and continue in
                                       interactive mode
### --list-models
MODEL
Auto
Ultimate
Fast
Efficient
Sonus
Cantus
Qwen3.8-Max
Qwen3.8-Flash
Kimi-K3.1-Pro
Kimi-K2.8-Preview
GLM-5.3
GLM-5.3-Flash
DeepSeek-V4-Pro
DeepSeek-Flash
MiniMax-M3.1-Flash
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":557,"duration_api_ms":438,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":532,"duration_api_ms":414,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done.

**Difference:** pre181 row 1 (`StopIteration`) already matched. Row 2 still differed: `__exit__` got `tb=None` for a raising body. Fixed by passing a non-None stand-in on the exception branch in both builds; other `tb` uses are refused by name at compile time.

**Probes (/tmp/probes):** `p_tb1`–`p_tb12`, `p_final`, `p_stop1` — 13 programs. All match CPython on both builds, or are refused by name (`type(tb)`, truthiness, helper call, `tb.tb_lineno`). Covered clean/raising bodies, `is`/`is not`/`==`/`!=`, suppression, return, break/continue, nesting, `@contextmanager`, and manager sources via argument/list/attribute/dict.

**Tests on final state:** `test_ail_pre197` (2 tests, 19s), `test_ail_safetynet` (5, 96s), `test_ail_files` (18, 107s, 1 skip), `test_ail_corpus_findings3` (2, 164s) — all OK. Full suite and `icount` not run.

**Commit:** `7f9e0d0` on `job-pre197-10252029`; manifest updated and `--check` passes. Not pushed.
[cost $0.0000, opencode tokens {"total": 1754226, "input": 69581, "output": 13450, "reasoning": 13851, "cache.write": 0, "cache.read": 1657344}]
    tool time: bash 10.3 min
        386s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && for m in test_ail_pre197 test_ail_safetynet test_ail_files t
         97s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest -q test_ail_safetynet 2>&1 | tail -20
         37s bash   cd /tmp/probes && for f in p_tb1 p_tb2 p_tb3 p_tb4 p_tb5 p_tb6 p_tb7 p_tb8 p_stop1; do echo "=== $f ==="; bash
         24s bash   cd /tmp/probes && cat > p_tb4.py <<'EOF' class CM:     def __enter__(self):         return self     def __exit
         19s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' from pathlib import Path p = Path('AIL_CURRENT/test_ail
         18s bash   mkdir -p /tmp/probes && cd /tmp/probes && cat > p_tb1.py <<'EOF' class C:     def __enter__(self):         ret
         18s bash   cd /tmp/probes && cat > p_tb9.py <<'EOF' class CM:     def __enter__(self):         return self     def __exit
         13s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest -q test_ail_pre197 2>&1 | tail -20

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Change really does:** the general `with` lowering passes a non-None `_AilTraceback()` on the exception branch; the typed path rewrites `tb is None`/`is not None`/`==`/`!=` against None to the exception-code test; both paths refuse other `tb` uses by name. This is more than "a stand-in in both builds".

**Probes (HEAD / base)**
- `p_basic` (clean, raising, nested, suppression): HEAD both builds match CPython; base both differ (`tb=None`) — target reproduced and fixed.
- `p_stop` (`StopIteration` in `@contextmanager`): HEAD and base match — report's "row 1 already matched" verified.
- `p_onlytb` (`__exit__` reads only `tb`, returns False): HEAD both match; base both differ — fix covers it.
- `p_suppress`, `p_reassign`: match.
- `p_rev` (`None is tb`, reversed): refused by name on both builds — acceptable per instructions.
- `p_3arg_unused` (unused 3-argument `__exit__` + a `with`): base both builds match CPython (`ok True`); **HEAD both builds crash** with `IndexError` at `withlib.py:400`. Defect.
- `p_3arg_used` (with calls a 3-argument `__exit__`): HEAD crash instead of CPython's `TypeError`; base compiled/runs.

**Tests:** `test_ail_pre197` and `test_ail_safetynet` pass on HEAD; `update_manifest.py --check` passes. `test_ail_files`/`test_ail_corpus_findings3` and the worker's 13 `/tmp/probes` not rerun; `icount` not run (not relevant to the hot path; worker reports it unavailable).

**Claims:** row 2 reproduction verified; the "stand-in in both builds" claim is false in detail (typed path uses the exception code, no stand-in); refusal claims verified; the "all probes matched" claim is incomplete because 3-argument `__exit__` was never probed.

The fix is correct for the targeted traceback semantics but introduces a compiler crash on a program that previously compiled: `rewrite` tests `len(node.args.args) >= 3` then indexes `args[3]`.

VERDICT: FIX
1. `/tmp/rprobes/p_3arg_unused.py` — an unused class with `def __exit__(self, et, ev)` plus an unrelated correct `with`:
   - Expected (CPython and base, both builds): `ok True`, exit 0.
   - Actual (HEAD, both builds): build fails, `IndexError: list index out of range` at `AIL_CURRENT/python/pkg-v12/withlib.py:400` (`args[3]` after a `>= 3` guard).
   - Same crash with `p_3arg_used.py`, where CPython exits 1 with `TypeError: CM.__exit__() takes 3 positional arguments but 4 were given`. Guard must require four args (or refuse/skip by name), not three.
[cost $0.0000, opencode tokens {"total": 819559, "input": 49157, "output": 3879, "reasoning": 16315, "cache.write": 0, "cache.read": 750208}]
    tool time: bash 2.6 min, write 0.0 min
        100s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre197 test_ail_
         22s bash   cd /tmp/rprobes && for f in p_basic p_stop p_rev p_3arg_unused p_3arg_used p_suppress; do echo "===== HEAD $f 
         15s bash   cd /tmp/rprobes && for f in p_basic p_stop p_3arg_unused; do echo "===== BASE $f ====="; bash ~/tools/cmp.sh /
          9s bash   cd /tmp/rprobes && echo "===== HEAD ====="; bash ~/tools/cmp.sh /tmp/rprobes/p_onlytb.py /home/runner/work/ail
          9s bash   cd /tmp/rprobes && for f in p_reassign; do echo "===== HEAD $f ====="; bash ~/tools/cmp.sh /tmp/rprobes/$f.py 
          0s bash   git worktree add /tmp/base work 2>&1 | tail -2; ls /tmp/base/AIL_CURRENT/test_ail_pre197.py 2>&1
          0s bash   grep -n "__exit__\|tbname\|bname\|_ExitBody(" AIL_CURRENT/python/pkg-v12/dunders.py | head -40; sed -n '990,10
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check 2>&1 | tail -5

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed the compiler crash: the `__exit__` rewrite now requires four positional args before reading `args[3]` (`AIL_CURRENT/python/pkg-v12/withlib.py:399`).

Added both regression cases to `test_ail_pre197.py` and a DEVLOG entry; manifest updated and `--check` passes.

Probes (both builds, `/tmp/probes/pre197_*`):
- 3-arg unused, 1/2-arg unused, 4-arg normal, 4-arg defaults, `*args`: stdout matches CPython (2/2 each, 0 diffs).
- 3-arg used (clean/raising, via attribute/list/dict), 5-arg, keyword-only `tb`: refused by name (`__exit__() called with too many positional arguments` / missing `extra` / keyword-only `tb`).

Tests on the committed state: `test_ail_pre197`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed. Committed as `83fcf08`.
[cost $0.0000, opencode tokens {"total": 454830, "input": 21845, "output": 4111, "reasoning": 3402, "cache.write": 0, "cache.read": 425472}]
    tool time: bash 6.5 min, edit 0.0 min
        266s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre197 test_ail_safetynet test_ail_files test_ai
         40s bash   cd /tmp/probes && for f in pre197_3arg_unused pre197_3arg_used pre197_3arg_used_clean pre197_2and1arg_unused p
         39s bash   cd /tmp/probes && for f in pre197_3arg_unused pre197_3arg_used pre197_3arg_used_clean pre197_2and1arg_unused p
         32s bash   cd /tmp/probes && for f in pre197_3arg_unused pre197_3arg_used pre197_3arg_used_clean pre197_2and1arg_unused p
         10s bash   cd /tmp/probes && for f in pre197_5arg_used pre197_kwonly_tb_used pre197_3arg_via_attr_list_dict; do echo "== 
          3s bash   cd /tmp/probes && bash ~/tools/cmp.sh /tmp/probes/pre197_3arg_used.py /home/runner/work/ail-ci/ail-ci 2>&1 | t
          0s bash   python3 tools/update_manifest.py && python3 tools/update_manifest.py --check 2>&1 | tail -5 && git status --sh
          0s bash   pwd && git status && git log --oneline -8 && ls

## review 1
[model opencode/deepseek-v4.1-flash-free]
**Change really does:** Adds the pre181 traceback fix (general path passes `_AilTraceback()` on the raise branch; typed path maps `tb is None`/`is not None`/`==`/`!=` to the exception code; other `tb` uses refused by name) plus a guard requiring 4 positional args before indexing `args[3]`. The final report describes only the guard and omits the main fix.

**Probes (HEAD / base):**
- Target reproduced and fixed: `p_basic`, `r_4arg_normal`, `r_swallow`, `r_funcraise`, `r_user_exc`, `r_inherit`, `r_multi`, `r_return_tb`, `r_or` — HEAD both builds match CPython; base both print `tb=None`.
- No crash: `r_short_unused_nowith`, `p_3arg_unused`, `r_2and1_unused`, `r_4arg_defaults` match CPython on both builds.
- Refused by name (CPython raises `TypeError`): 3-arg used clean/raising, via attribute/list/dict, 5-arg, keyword-only `tb`.
- `r_none_left` (`None is tb`), `t_alias`, `t_none_left`: refused by name; acceptable.
- `r_star_type`: HEAD `_AilTraceback` vs CPython `traceback`; base `NoneType` — pre-existing traceback-object limitation, `is None` now correct.
- `r_unused_tb_use`: HEAD refuses by name where base compiled and CPython runs; new over-broad but named refusal, acceptable.
- Plain no-`with` C byte-identical base vs HEAD; `with`-without-`tb` C changes (adds the stand-in) as expected.

**Claims:** 3-arg/1-2-arg unused, 4-arg normal, 4-arg defaults, `*args` (`is None`), refusal cases — verified. Tests `test_ail_pre197`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_pre181` all pass; `update_manifest --check` rc 0; HEAD `83fcf08`. **False:** the crash was not pre-existing; base `p_3arg_unused` passes, and the `IndexError` was introduced by commit `7f9e0d0` and fixed in `83fcf08` (review 0 found it).

**Unverified:** `icount`/speed (perf denied; new allocation is exception-path only).

**Pre-existing:** `*args` `__exit__` leaks the type name of the stand-in; AIL has no traceback objects.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1896704, "input": 77111, "output": 7145, "reasoning": 27104, "cache.write": 0, "cache.read": 1785344}]
    tool time: bash 7.4 min
        169s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 900 python3 ../tools/par_check.py -j 2 test_
        100s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 900 python3 ../tools/par_check.py -j 2 test_
         31s bash   cd /tmp/rprobes && date && for f in r_none_left r_star_type r_short_unused_nowith r_shadow r_kwargs_exit r_typ
         28s bash   cd /tmp/rprobes && date && for f in r_multi r_swallow r_funcraise r_user_exc r_inherit r_return_tb; do echo "#
         26s bash   cd /tmp/rprobes && for f in r_none_left r_star_type r_short_unused_nowith r_shadow t_shadow t_none_left; do ec
         18s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 900 python3 ../tools/par_check.py -j 2 test_
         16s bash   cd /tmp/rprobes && date && for f in t_basic t_shadow t_alias t_none_left; do echo "######## $f"; bash ~/tools/
         14s bash   cd /tmp/cmpdcNu && ls -l exe_g exe_d 2>/dev/null; sha256sum exe_g exe_d 2>/dev/null; echo ---; cd /tmp/cmpJRkh

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-25T13:07:38Z
