# job job-qtest3-10241647  started 2026-10-24T07:47:48Z  worker=oc reviewer=oc (GitHub)
## qoder discovery
1.1.73
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
Failed to fetch model list: The QODER_PERSONAL_ACCESS_TOKEN environment variable contains a token that was rejected. It overrides any saved login, so unset it or set a valid token, then restart.
deepseek-v4.1-flash -> An unexpected critical error occurred:QoderAuthError: The QODER_PERSONAL_ACCESS_TOKEN environment variable contains a token that was rejected. It overrides any saved login, so unset it or set a valid token, then restart.     at bue (file:///usr/local/lib/node_modules/@qoder-ai/qodercli/bundle/qoderc
DeepSeek-V4.1-Flash -> An unexpected critical error occurred:QoderAuthError: The QODER_PERSONAL_ACCESS_TOKEN environment variable contains a token that was rejected. It overrides any saved login, so unset it or set a valid token, then restart.     at bue (file:///usr/local/lib/node_modules/@qoder-ai/qodercli/bundle/qoderc

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed as `12e8fa9` on `job-qtest3-10241647`.

**Cause:** the general-path `_ail_partition` / `_ail_rpartition` helpers called `len(sep)` before `find(sep)`, so int/float/None separators raised `TypeError: object of type 'int' has no len()` instead of CPython’s `TypeError: must be str, not int`. Reordered the checks; empty separators still raise `ValueError: empty separator`.

**Probes:** 12 programs in `/tmp/probes/` covering missing/empty/repeated/multi-character/huge separators, both operations, nesting, and separators passed via argument, list item, attribute and dict value. All 12 now match CPython on both builds (`g` and `d`). The only difference seen was p08 (wrong-type separator messages); bytes/list cases already matched.

**Tests:** `test_ail_qtest3` + `test_ail_corpus_findings3` 4/4 OK; `test_ail_safetynet` + `test_ail_files` 23/23 OK (1 skipped, no zig); `test_ail_tuples` 26/26 OK. Manifest `--check` passes.

No other differences found.
[cost $0.0000, opencode tokens {"total": 1117381, "input": 53800, "output": 6694, "reasoning": 4599, "cache.write": 0, "cache.read": 1052288}]
    tool time: bash 12.9 min
        261s bash   python3 -m unittest -v test_ail_safetynet test_ail_files > /tmp/t_sn.log 2>&1; rc=$?; tail -30 /tmp/t_sn.log; 
        228s bash   python3 -m unittest -v test_ail_qtest3 test_ail_corpus_findings3 > /tmp/t_q3.log 2>&1; rc=$?; tail -25 /tmp/t_
        121s bash   python3 -m unittest -v test_ail_tuples > /tmp/t_tuples.log 2>&1; rc=$?; tail -15 /tmp/t_tuples.log; echo rc=$r
         72s bash   for p in /tmp/probes/p*.py; do echo "=== $p"; bash ~/tools/cmp.sh "$p" "$PWD" 2>&1 | grep -E "cpython exit|bui
         33s bash   for p in /tmp/probes/p08.py /tmp/probes/p03.py /tmp/probes/p04.py /tmp/probes/p05.py; do echo "=== $p"; bash ~
         21s bash   cat > /tmp/probes/p11.py <<'EOF' def part(s, sep):     return s.partition(sep)   def rpart(s, sep):     return
         15s bash   bash ~/tools/cmp.sh /tmp/probes/p08.py "$PWD" 2>&1 | tail -40
         15s bash   cat > AIL_CURRENT/test_ail_qtest3.py <<'EOF' """str.partition / str.rpartition: non-str separators must raise 

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change does:** In `AIL_CURRENT/python/pkg-v12/tuplegen.py`, the generated `_ail_partition` / `_ail_rpartition` helpers now run `find`/`rfind` before the `len(sep) == 0` check, so non-`str` separators get `find`'s `TypeError: must be str, not ...` instead of `object of type ... has no len()`. Empty separators still raise `ValueError: empty separator`. No runtime/C code change.

**Probes (HEAD, both g/d unless noted):**
- `a_core`, `f_huge`, `h_mutation`, `n_bmp`, `m_int64`: missing/empty/repeated/multi-char/huge/BMP-unicode separators, mutation and nesting — all match CPython.
- `b_types`, `o_emptyrecv`: int/float/None/bool/bytes/bytearray/list/tuple/dict, empty receiver — HEAD matches; base differs exactly on the old `has no len()` messages.
- `c_channels`, `d_empty`, `p_userclass`, `q_setrange`: argument/list/attr/dict channels, empty sep, user-class/set/range seps — all match.
- Worker's `p01`–`p12`: all match on HEAD; only `p08` differs on base. Claim verified.
- `i_nofeature`: `program.c` byte-identical to base on g and d; no overhead for programs not using the feature.

**Report audit:** cause/fix, empty-separator `ValueError`, “only p08 differed”, tests, and manifest `--check` all verified. “No other differences” verified for partition semantics; unrelated pre-existing limits below.

**Pre-existing (identical on `/tmp/base`):** `str`-subclass inheritance, non-BMP literals on the general path, `object`/function/`complex`/no-`__init__`-class separators are refused by name; `10**100` literals abort with `integer overflow`.

**Tests:** `test_ail_qtest3`, `test_ail_safetynet`, `test_ail_corpus_findings3`, `test_ail_files` (4 modules, 0 failed) and `test_ail_tuples` (0 failed). Manifest `--check` rc 0.

**Note:** `test_ail_qtest3` is not in `ail_check.MODULES`/CI shards, matching prior job modules such as `test_ail_fuzz45` and `test_ail_corpus_findings3`; not counted as a defect.

**Unverified:** instruction counts — `perf_event_open` is denied on this runner. The change only reorders two checks in a cold helper and `find("")` is O(1), so no hot-path effect is expected.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1996964, "input": 58894, "output": 10532, "reasoning": 17138, "cache.write": 0, "cache.read": 1910400}]
    tool time: bash 14.4 min, write 0.0 min
        259s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_qtest3 test_ail_safetynet test_ail_corpus_findin
        119s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_tuples 2>&1 | tail -10; date
         88s bash   date; for p in /tmp/probes/p*.py; do r=$(bash ~/tools/cmp.sh "$p" "$PWD" 2>&1); if echo "$r" | grep -q "DIFF";
         88s bash   date; for p in /tmp/probes/p*.py; do r=$(bash ~/tools/cmp.sh "$p" /tmp/base 2>&1); if echo "$r" | grep -q "DIF
         70s bash   mkdir -p /tmp/speed; cd /tmp/speed; for prog in g01_030 g15_010; do for side in head base; do if [ $side = hea
         51s bash   date; for p in /tmp/rprobes/*.py; do echo "=== $(basename $p)"; bash ~/tools/cmp.sh "$p" "$PWD" 2>&1 | grep -E
         31s bash   date; for p in /tmp/rprobes/a_core.py /tmp/rprobes/b_types.py /tmp/rprobes/d_empty.py /tmp/rprobes/c_channels.
         30s bash   date; for wt in "$PWD" /tmp/base; do echo "=== $([ "$wt" = "$PWD" ] && echo HEAD || echo BASE)"; bash ~/tools/

FINAL VERDICT: ACCEPT  2026-10-24T08:19:01Z
