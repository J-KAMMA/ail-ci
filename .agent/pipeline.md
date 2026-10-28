# job job-stdlib23-10290511  started 2026-10-28T20:28:13Z  worker=oc reviewer=oc (GitHub)
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
Qwen3.8-Flash
DeepSeek-Flash
DeepSeek-Flash -> ts":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["Your personal Credits have been exhausted. Please check your plan."],"error_code":118,"fast_mode_state":"off","uuid":"4d2a6292-9459-400a-aac9-5c2934f84f94","session_id":"b19dcaef-2472-4e25-8f31-d8dbf8d43466"}
DeepSeek-Flash -> input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your credit usage limit. Please upgrade your subscription plan to get more resources. Report Issue (input /feedback)"],"error_code":118,"fast_mode_state":"off","uuid":"6cf500f5-cc4b-4330-8feb-03b5f01d3f22","session_id":"7dfe74bd-9ae8-40f0-a2d0-e2e5a83d823d"}

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Implemented and committed as `7fd7527`.

- Chose `tempfile` (7 imports, the most-used still-refused module) and lowered `gettempdir`, `mkdtemp`, and `TemporaryDirectory` onto the existing `os` file layer via `tempfilelib.py` + `prelude_tempfile.py`. Other names/options remain named refusals.
- Added `test_ail_stdlib24.py` (the requested `stdlib23` file already covers argparse) with 5 CPython-comparison programs on both builds and 2 refusal cases; registered it in `MODULES` and CI shards.
- Tests on final commit: group 1 (stdlib5, safetynet) 15 passed; group 2 (stdlib23, stdlib24, files, corpus_findings3, python_syntax, check) 41 passed, 1 skipped.
- Probes: `tf_basic`, `tf_context`, `tf_empty`, `tf_env`, `tf_error`, `tf_positional`, `tf_routes`, `tf_alias` match CPython on both builds; `tf_refuse` (NamedTemporaryFile), `tf_refuse2` (mkstemp), and `tf_types` (non-str literal) are refused by name.
- `update_manifest.py --check` and `ci_shards.py --check` pass. Random temp names are equivalent, not CPython-identical.
[cost $0.0681, opencode tokens {"total": 6377758, "input": 150230, "output": 17823, "reasoning": 27177, "cache.write": 0, "cache.read": 6182528}]
    tool time: bash 28.2 min
       1152s bash   cd AIL_CURRENT && (python3 -m unittest test_ail_stdlib5 test_ail_safetynet > /tmp/group1.log 2>&1; echo $? > /
        135s bash   python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/test_ail_stdlib24.py') s=p.read_text() s=s.repla
        118s bash   cat > /tmp/probes/tf_types.py <<'PY' import tempfile   def main() -> None:     print(tempfile.mkdtemp(prefix=1
        104s bash   python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/python/pkg-v12/prelude_tempfile.py') s=p.read_te
         45s bash   python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/python/pkg-v12/prelude_tempfile.py') s=p.read_te
         34s bash   python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/python/pkg-v12/prelude_tempfile.py') s=p.read_te
         28s bash   mkdir -p /tmp/probes cat > /tmp/probes/tf_basic.py <<'PY' import os import tempfile   def main() -> None:     
         22s bash   cat > /tmp/probes/tf_positional.py <<'PY' import os import tempfile   class Box:     prefix: str      def __in

## review 0
[model opencode-go/deepseek-v4.1-flash]
**Review report**

The change really does: add `tempfile` to the stdlib5 pass and lower `gettempdir`, `mkdtemp`, `TemporaryDirectory` onto `os` via `prelude_tempfile.py`/`tempfilelib.py`; the range `work..HEAD` also contains the earlier argparse commit `390f700`. Report is accurate about the lowering, but it overstates CPython equivalence.

Verified claims: tempfile is the most-used still-refused import (counts: argparse 9, tempfile 7, struct 6); other names are named refusals (`NamedTemporaryFile`, `gettempprefix`, `ignore_cleanup_errors=` observed); `test_ail_stdlib24` registered and passing; `update_manifest.py --check` and `ci_shards.py --check` pass; a program without `tempfile` has identical `program.c` and identical exe sha256 on base vs HEAD. Tests: `test_ail_stdlib24` 0 failed; `test_ail_stdlib23`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_stdlib5` 0 failed. `test_ail_safetynet` not re-run (time).

Defects (all compile and run on HEAD; base refuses these programs, so the change caused them):

1. `TemporaryDirectory` has no `__del__` finalizer. `/tmp/rprobes/tf_del.py`:
   `def make() -> str: t = tempfile.TemporaryDirectory(prefix='ail-del-'); return t.name` then `print(os.path.isdir(make()))` and the same via `tempfile.TemporaryDirectory(...).name`.
   Expected CPython: `False` / `False`; actual HEAD: `True` / `True` (directories leak; CPython removes on GC).

2. Explicit `dir=''` is treated as "no dir". `/tmp/rprobes/tf_emptydir.py`: `d = tempfile.mkdtemp(dir=''); print(os.path.dirname(d))`.
   Expected CPython: the current working directory (e.g. `/tmp/cmpXXXX`); actual HEAD: `/tmp`. `_ail_tempfile_mkdtemp` special-cases `dir == ''`, but CPython only defaults on `None`.

3. `mkdtemp` does not return `abspath`. `/tmp/rprobes/tf_reldir.py`: `os.mkdir('reldir'); d = tempfile.mkdtemp(dir='reldir'); print(os.path.dirname(d))`.
   Expected CPython: absolute `/tmp/cmpXXXX/reldir`; actual HEAD: `reldir`.

4. Bytes arguments are neither supported nor refused. `/tmp/rprobes/tf_bytes.py`: `data = b'bp-'; d = tempfile.mkdtemp(prefix=data); print(type(d).__name__, os.path.isdir(d))`.
   Expected CPython: `bytes True`; actual HEAD: `TypeError` (bytes reach the prelude; it should be a named refusal like the literal case).

Unverified: argparse semantics (`390f700`) beyond its test module; `test_ail_safetynet`.

VERDICT: FIX
[cost $0.0248, opencode tokens {"total": 1165781, "input": 48916, "output": 5842, "reasoning": 17775, "cache.write": 0, "cache.read": 1093248}]
    tool time: bash 23.6 min
        729s bash   cd /home/runner/work/ail-ci/ail-ci && time python3 tools/par_check.py -j 2 test_ail_stdlib23 test_ail_files te
        180s bash   sleep 180; date; ps aux | grep -c '[p]ar_check'; tail -40 /tmp/rp_tests.log
        120s bash   cd /home/runner/work/ail-ci/ail-ci && nohup python3 tools/par_check.py -j 2 test_ail_stdlib24 test_ail_stdlib2
         98s bash   cd /home/runner/work/ail-ci/ail-ci && time python3 tools/par_check.py -j 2 test_ail_stdlib24 2>&1 | tail -20
         61s bash   cd /home/runner/work/ail-ci/ail-ci && for p in tf_rel tf_types tf_cleanup tf_missing; do echo "=== $p"; timeou
         60s bash   sleep 60; date; ps aux | grep -c '[p]ar_check'; tail -30 /tmp/rp_tests.log
         49s bash   cd /tmp/rprobes && cat > tf_reldir.py <<'PY' import os import tempfile  def main() -> None:     os.mkdir('reld
         48s bash   cd /home/runner/work/ail-ci/ail-ci && for p in tf_del tf_patharg tf_missing2 tf_collide tf_ignore; do echo "==

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed all four review defects and committed as `40b5fed`.

- `dir=''` now means cwd; `mkdtemp` returns `abspath`; bytes args are named compile-time refusals; dropped `TemporaryDirectory` (the GC-finalizer lifetime AIL lacks) is now a named refusal instead of leaking, while `with` and explicit `.cleanup()` stay supported. `__exit__` now returns `None`.
- Probes (both builds): 7 match CPython (`tf_emptydir`, `tf_reldir`, `tf_lifecycle`, `tf_dir_none`, `tf_empty_td`, `tf_values`, `tf_plain`), 7 refused by name (`tf_del`, `tf_bytes`, `tf_bytes_{arg,list,dict,attr}`, `tf_refuse`).
- Final tests after commit: `test_ail_stdlib24`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed. `update_manifest.py --check` and `ci_shards.py --check` pass.
[cost $0.0424, opencode tokens {"total": 2660006, "input": 85376, "output": 12589, "reasoning": 24057, "cache.write": 0, "cache.read": 2537984}]
    tool time: bash 25.9 min, write 0.0 min
        673s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_stdlib24 test_ail_safetynet tes
        309s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_stdlib24 test_ail_safetynet tes
        135s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/par_check.py -j 2 test
        108s bash   cd /tmp/probes && cat > tf_lifecycle.py <<'PY' import os import tempfile   def main() -> None:     t = tempfil
         96s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_stdlib24 2>&1 | tail -40
         82s bash   cd /tmp/probes && for p in tf_del tf_emptydir tf_reldir tf_bytes tf_bytes_arg tf_bytes_list tf_bytes_dict tf_b
         80s bash   mkdir -p /tmp/probes && cd /tmp/probes && cat > tf_del.py <<'PY' import os import tempfile   def make() -> str
         39s bash   cd /tmp/probes && for p in tf_del tf_emptydir tf_reldir tf_bytes; do echo "===== $p"; bash ~/tools/cmp.sh /tmp

## review 1
[model opencode-go/deepseek-v4.1-flash]
**Review report**

The change adds `tempfile` to the stdlib5 pass (`argparse` in the same range is the earlier `390f700`) and lowers `gettempdir`/`mkdtemp`/`TemporaryDirectory` onto `os` via `tempfilelib.py` + `prelude_tempfile.py`, then fixes the four prior defects. It really does that; the report understates one point: the lifetime check is purely syntactic, so some GC-lifetime uses are still accepted and leak.

Verified claims (probes in `/tmp/rprobes`, `/tmp/probes`; both AIL_IR=0/1):
- `dir=''` means cwd, relative `dir=` yields an absolute path: `tf_emptydir`, `tf_reldir`, `tf_empty_td`, `tf_dir_none`, `tf_values`, `tf_plain`, `tf_lifecycle` all same stdout as CPython. Verified.
- bytes arguments refused by name: `tf_bytes`, `tf_bytes_arg/list/dict/attr` all show `tempfile.mkdtemp(prefix=) is built for str values only (bytes is not built)`. Verified.
- simple dropped `TemporaryDirectory` refused by name: `tf_del` shows the named note. Verified, but see defect 2.
- `__exit__` returns `None`: `tf_lifecycle` matches CPython. Verified.
- Non-feature program: `r_plain.py` (contains the words `tempfile`/`argparse` but imports neither) has byte-identical `program.c` and exe on `work` vs HEAD. Verified.
- Tests: `test_ail_stdlib23`, `test_ail_stdlib24`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 5 modules, 0 failed. Manifest and ci_shards `--check` pass. Verified (report said 4 modules; I added stdlib23).

Defects (both builds; base `/tmp/rbase` refuses `tempfile`, so the change caused these):

1. `None` is only treated as the default when it is a literal. Through a variable, list item or dict value it reaches the prelude and raises a runtime `TypeError` instead of CPython's default. `/tmp/rprobes/r_none_var.py`:
   `s = None; p = None; d = None`
   `name = tempfile.mkdtemp(suffix=s, prefix=p, dir=d)`
   `print(os.path.isabs(name), os.path.basename(name).startswith('tmp'))`
   Expected CPython: `True True`, exit 0. Actual: exit 1, `TypeError: tempfile.mkdtemp() is built for str arguments only`. Same for `r_none_list.py` (list item), `r_none_dict.py` (dict value) and `r_none_td.py` (TemporaryDirectory `suffix=`).

2. The "lifetime is explicit" test is syntactic, so dropped objects still leak while returning wrong stdout (the report says dropped objects are refused instead of leaking):
   - `/tmp/rprobes/r_td_reassign.py`: `t = TemporaryDirectory(prefix='r-a-'); a = t.name; t = TemporaryDirectory(prefix='r-b-'); b = t.name; t.cleanup(); print(os.path.isdir(a), os.path.isdir(b))`. Expected CPython `False False`; actual `True False`.
   - `/tmp/rprobes/r_td_deadcleanup.py`: `t = TemporaryDirectory(...); if False: t.cleanup(); return t.name`, then `print(os.path.isdir(p))`. Expected `False`; actual `True`.
   Both compile (not refused) and exit 0 with the wrong answer.

Pre-existing: none observed.

Unverified: argparse semantics beyond `test_ail_stdlib23`; Windows `gettempdir` candidates; speed (no hot code touched); `r_path_dir.py` (a `pathlib.Path` `dir=` is refused, but for unrelated `os.path` reasons, so not counted).

VERDICT: FIX
1. Treat non-literal `None` for `suffix`/`prefix`/`dir` as the CPython default (or refuse it by name at compile time); `r_none_var`/`r_none_list`/`r_none_dict`/`r_none_td` currently die with a runtime `TypeError` while CPython succeeds.
2. Refuse `TemporaryDirectory` lifetimes that the syntactic check cannot prove, e.g. a reassigned binding (`r_td_reassign`: expected `False False`, actual `True False`) and a cleanup in a dead branch (`r_td_deadcleanup`: expected `False`, actual `True`); both leak silently.
[cost $0.0219, opencode tokens {"total": 944691, "input": 54687, "output": 4454, "reasoning": 13998, "cache.write": 0, "cache.read": 871552}]
    tool time: bash 16.5 min
        729s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1500 python3 ../tools/par_check.py -j 2 test_a
        107s bash   date; cd /tmp/probes && for p in tf_emptydir tf_reldir tf_dir_none tf_empty_td tf_values tf_plain tf_lifecycle
         83s bash   date; cd /tmp/rprobes && for p in r_none_var r_none_list r_none_dict r_none_td r_td_reassign r_td_deadcleanup;
         45s bash   date; cd /tmp/probes && for p in tf_del tf_bytes tf_bytes_arg tf_bytes_list tf_bytes_dict tf_bytes_attr; do ec
         13s bash   date; cd /tmp/rprobes && for spec in "r_path_dir /home/runner/work/ail-ci/ail-ci" "r_none_var /tmp/rbase"; do 
         12s bash   cd /home/runner/work/ail-ci/ail-ci; rm -rf /tmp/rdbg/base_db /tmp/rdbg/head_db; for tag in base head; do if [ 
          1s bash   date; cd /home/runner/work/ail-ci/ail-ci; rm -rf /tmp/rdbg; mkdir -p /tmp/rdbg; for tag in base head; do if [ 
          0s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 300 python3 tools/update_manifest.py --check 2>&1 | tail -3; dat

FINAL VERDICT: FIX  2026-10-28T23:11:48Z
