# job job-pre407-10281133  started 2026-10-28T02:33:41Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> uests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You have reached the daily usage limit. Please try again later."],"error_code":110,"fast_mode_state":"off","uuid":"9611643b-aa8a-4e21-a318-bb0c4c21891c","session_id":"3ab53196-87ae-46e8-b6b8-2b8a89d03c0b"}
DeepSeek-Flash -> l_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your daily usage limit for Chat. Come back tomorrow to continue working with me. Report Issue (input /feedback)"],"error_code":110,"fast_mode_state":"off","uuid":"95ffdfdc-db5e-497b-a169-06e1dbc0a045","session_id":"d2296da9-efd2-4708-8e07-bb4cf00dfe63"}

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Committed `0720f07` on `job-pre407-10281133`.

- Fixed `r10`: attribute-held container items read before a later store are now folded and refused by name on both builds; class-held containers and source-order rebinds are covered too.
- Deferred function/lambda/method bodies are guarded, so the pre401 `q2` false-refusal regression does not recur; `q2`/`q3` match CPython.
- Added `test_ail_pre407.py`: 16 refused, 10 matching programs.
- Probes: 39 runs / 38 unique; 15 match, 22 refused by name, 2 remain pre-existing runtime `integer overflow` (`p05` argument-held list literal, `p07` local alias of the held list).
- Final required tests on the commit: 4 modules, 0 failed (`test_ail_pre407`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`).
- `tools/update_manifest.py --check` passes; no push.
[cost $0.0000, opencode tokens {"total": 11344737, "input": 347157, "output": 30949, "reasoning": 60263, "cache.write": 0, "cache.read": 10906368}]
    tool time: bash 28.7 min, grep 0.0 min, write 0.0 min
        354s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_pre407 test_ail_safetynet test_
        274s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/par_check.py -j 2 test
        274s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_pre407 test_ail_safetynet test_
        273s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_pre407 test_ail_safetynet test_
         77s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/pre407/*.py; do out=$(bash ~/tools/cmp.sh "$p" "$PW
         58s bash   python3 -m unittest -v /tmp/test_ail_pre401_ref.py
         58s bash   cd /tmp && python3 - <<'PY' from pathlib import Path p=Path('/tmp/test_ail_pre401_ref.py') s=p.read_text() s=s
         58s bash   python3 -m unittest -v /tmp/test_ail_pre401_ref.py

## review 0
[model opencode/deepseek-v4.1-flash-free]
Diff in one line: it replays module-level attribute/subscript stores on known instances/classes in source order, folding container items for `int()` checks, with guards for deferred bodies.

**Defect (introduced by this change)**
1. A module-level store value survives a later mutation that the replay does not model (alias subscript, tuple target, nested subscript, dict alias), so a read *after* the mutation still folds the stale value and is refused. Base compiles all of these and matches CPython.

```
# r10
class C: pass
c = C(); c.v = [1e300]
a = c.v; a[0] = 1.5
print(int(c.v[0]))
```
Expected CPython/base: `1`; HEAD: both builds fail with `int() of a float outside int64: 1e+300`.

Same defect with `c.v[0], x = 1.5, 0` (r12), `c.v = [[1e300]]; c.v[0][0] = 1.5; print(int(c.v[0][0]))` (r11), and `c.d = {"k": 1e300}; a = c.d; a["k"] = 1.5; print(int(c.d["k"]))` (r13). All expected `1`, all refused by name on HEAD, all match CPython on base.

**Pre-existing (identical on base, not blocking)**
- `self.v = [1e300]` read directly/mutated through a local list alias, `if`, class body, subclass store, or `for` remains a false refusal on base too.
- `p05`/`p07` runtime `integer overflow` confirmed on base.

**Claims**
- Fixed recorded `r10`: verified (HEAD refuses by name, base exits 1 with `integer overflow`).
- `q2`/`q3` no false-refusal regression: verified, match CPython on HEAD.
- 16 refused / 10 matching in `test_ail_pre407.py`: verified.
- 4 required modules, 0 failed: verified.
- Manifest `--check`: verified, exit 0.
- Direct source-order rebinds and class-held containers: partly true; coverage is incomplete as shown by the defect above.
- Worker's 39-probe tally: unverified (only its own probes).

No-feature program: generated `program.c` is byte-identical to base; only `native_report.json` paths differ. Speed not checked: change is compile-time-only.

VERDICT: FIX

1. Stale folded value after an untracked mutation; probes r10, r12, r11, r13 above, expected `1`, actual compile-time refusal `int() of a float outside int64: 1e+300` on both builds.
[cost $0.0000, opencode tokens {"total": 927054, "input": 41936, "output": 4296, "reasoning": 13622, "cache.write": 0, "cache.read": 867200}]
    tool time: bash 6.0 min, write 0.0 min
        274s bash   python3 ../tools/par_check.py -j 2 test_ail_pre407 test_ail_safetynet test_ail_files test_ail_corpus_findings3
         39s bash   for f in case_r10 p05 p07 q2 q3; do for wt in "$PWD" /tmp/base; do echo "=== $f @ ${wt##*/}"; cd "$wt"; bash ~
         19s bash   for wt in "$PWD" /tmp/base; do echo "######## $wt"; cd "$wt"; for p in /tmp/rprobes/r1*.py; do echo "=== $(bas
         10s bash   cd /tmp/base && for p in /tmp/rprobes/r0*.py; do echo "=== $(basename $p)"; bash ~/tools/cmp.sh "$p" "$PWD" 2>
         10s bash   for p in /tmp/rprobes/r0*.py; do echo "=== $(basename $p)"; bash ~/tools/cmp.sh "$p" "$PWD" 2>&1 | grep -E '^(
          9s bash   cd /home/runner/work/ail-ci/ail-ci; for f in q2 q3; do echo "=== $f HEAD"; bash ~/tools/cmp.sh /tmp/probes/pre
          2s bash   rm -rf /tmp/dbg_head /tmp/dbg_base /tmp/nfhead /tmp/nfbase; mkdir -p /tmp/nfhead /tmp/nfbase; cp /tmp/rprobes/
          0s bash   git merge-base --is-ancestor work HEAD && echo ancestor; git worktree add /tmp/base work 2>&1 | tail -3; date

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed the reviewer defect and committed on `job-pre407-10281133`.

- `08b5ac9` aliased container mutations now replay in source order; unapplied stores invalidate instead of leaving stale values.
- `b49f173` corrected the DEVLOG probe tally.

Probes (`bash ~/tools/cmp.sh`, both builds, 24 programs):
- Match CPython (19): `r10`, `r11`, `r12`, `r13`, alias chain/list-item/attribute/dict-value, class alias, `__init__` alias/nested, nested dict alias, negative, boundary, delete, dict `update`, empty+append, slice, tuple-attribute, second instance.
- Refused by name (5): `alias_append`, `alias_augassign`, `two_instances_alias`, `alias_read_before_mutation`, `alias_plain_scalar_between`.
- All reviewer cases `r10`–`r13` now print `1` and match CPython on both builds.

Final-commit tests: `test_ail_pre407`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed. Manifest `--check` exits 0. No push.
[cost $0.0000, opencode tokens {"total": 1809813, "input": 78001, "output": 11294, "reasoning": 29382, "cache.write": 0, "cache.read": 1691136}]
    tool time: bash 14.7 min
        293s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre407 test_ail_
        291s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre407 test_ail_
         92s bash   cd /home/runner/work/ail-ci/ail-ci && for p in r10 r11 r12 r13 alias_append alias_dict_update alias_chain alia
         86s bash   cd /home/runner/work/ail-ci/ail-ci && for p in r10 r11 r12 r13 alias_append alias_augassign alias_via_attr ali
         62s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre407 2>&1 | ta
         23s bash   cd /home/runner/work/ail-ci/ail-ci && for p in r10 r11 r12 r13 alias_append alias_augassign alias_via_attr; do
         19s bash   mkdir -p /tmp/probes && cd /tmp/probes && cat > r10.py <<'EOF' class C: pass c = C(); c.v = [1e300] a = c.v; a
         18s bash   cd /home/runner/work/ail-ci/ail-ci && for p in r10 r11 r12 r13; do echo "=== $p"; bash ~/tools/cmp.sh /tmp/pro

## review 1
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
## Review: pre407

**What the change really does:** it adds a `_KnownContainerStores` replay to the `int()`-int64 checker that walks direct module-level statements, applies constant attribute/subscript/container-method stores to per-instance/per-class override values in source order, invalidates what it cannot apply, and drops those overrides inside function/lambda/class bodies (plus stops treating module-level attribute stores as "unsafe" class stores). All effects are compile-time refusal decisions; generated C is untouched. That matches the report's description.

**Defect found (caused by the change).**

`_apply_augassign` (ail_chatgpt.py:1217) assigns `container[key] = value` after a successful static read without checking the container is mutable. When the attribute holds a tuple/str/bytes, the compiler raises an uncaught `TypeError` and dies with a traceback instead of compiling (base compiles and the program fails at run time exactly like CPython).

Probe `/tmp/rprobes/q1_tuple_aug.py`:
```
class C:
    pass
c = C()
c.t = (1, 2)
c.t[0] += 1
print(c.t)
```
- CPython and **base** both builds: compile, exit 1, `TypeError: 'tuple' object does not support item assignment`.
- **HEAD** both builds: build fails with `File "ail_chatgpt.py", line 1217, in _apply_augassign ... TypeError: 'tuple' object does not support item assignment` — a compiler crash, not a named refusal.

Same crash: `q2_str_aug` (`c.s = "ab"; c.s[0] += "x"`), `q3_bytes_aug` (`c.b = b"ab"; c.b[0] += 1`), and `p12_classbody_aug` (`class C: t = (1, 2)` / `C.t[0] += 1`). All compile on base.

**Claims.**
- "replay in source order; unapplied stores invalidate" — verified for aliases/tuple targets/nested/dict/slice/`update`: `r10_alias_store`, `r11_nested`, `r12_tuplemut`, `r13_dict_alias_store` and my `p4`–`p7` match CPython on both builds; **false** for immutable containers (crash above).
- "all reviewer cases r10–r13 print 1 and match CPython" — verified. The original pre407 `r10` (`p1_r10`) is now refused by name (`int() of a float outside int64`), so the recorded difference is closed by refusal, as the task allows.
- "24 probes, 19 match / 5 refused" — partially verified: `/tmp/probes` holds 24 files; my spot checks of the same routes agree. Not re-run in full.
- "test_ail_pre407 + test_ail_safetynet, 0 failed" — verified on HEAD (`-j 2`, 2 modules, 0 failed).
- "test_ail_files + test_ail_corpus_findings3, 0 failed" — unverified (reviewer rules; not rerun).
- "manifest `--check` exits 0" — verified.
- Non-feature C unchanged: `g00_000`, `g00_002`, `g01_008` `--debug-dir` `program.c` byte-identical to base (only temp paths in `native_report.json` differ), so no icount check needed.

**Pre-existing (identical on base, not blocking):** `p2_ifstore`/`p3_loopstore` refused by name while CPython prints 1; `p11_formut` (`for x in c.v: c.v[0] = x`) runtime `integer overflow` on both; `p9_localalias` and `p8_plain` match on both.

**Unverified:** full 24-probe tally, `test_ail_files`/`test_ail_corpus_findings3`, and the `/tmp/probes/pre407` 39-run tally.

VERDICT: FIX
1. Compiler crash (uncaught `TypeError`) on module-level or class-body augmented subscript assignment into an attribute-held immutable container (`tuple`/`str`/`bytes`). Probe `q1_tuple_aug.py` above (also `q2_str_aug.py`, `q3_bytes_aug.py`, `p12_classbody_aug.py`): expected base/CPython behaviour — program compiles and dies at run time with `TypeError: 'tuple' object does not support item assignment` (exit 1); actual — build fails in both `g` and `d` with a traceback at `ail_chatgpt.py:1217`, `_apply_augassign` → `container[key] = value`. The store replay must invalidate (or skip) when the materialized container is not a list/dict.

FINAL VERDICT: FIX  2026-10-28T04:13:00Z
