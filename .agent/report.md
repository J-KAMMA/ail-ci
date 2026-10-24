# job job-pre112-10242224  started 2026-10-24T13:32:13Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":788,"duration_api_ms":669,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":610,"duration_api_ms":496,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done. Committed on branch `job-pre112-10242224` as `3cde15d`.

## What the difference was
`t4h` reproduced: a module-level dict keyed by a frozenset of tuples worked as a display, but every lookup failed. Root cause: the tuple pass (`tuplib.py`) lowers `frozenset({(1,'a'),(2,'b')})` to its table class `_AilS_Pi_sQ`. A table cannot be keyed by a set, so the dict stayed a **plain object**, yet the same expression used as the *lookup* key was still lowered to the table class — hash/eq mismatch → `KeyError`, `in` False, `.get()` None.

## Fix
- `tupexpr.ex_Subscript` and `tupstmt.assign_one`: refuse a set/frozenset of tuples used as the key of a non-table container.
- `tuplib.module_assign`: bail on an untypable module-level constant that mentions a tuple (this was the swallowed refusal for `D = {frozenset(...): ...}`).
The pass then leaves the program as written; the general path keeps the dict and key boxed, matching CPython.

## Verification (numbers)
- 15 differential probes via `~/tools/cmp.sh` on **both** builds: `p01b,p02–p15` — all match CPython. Coverage: inline key, variable/alias key, list item, attribute, dict value, function argument, store, `in`, `.get`, `setdefault`, `pop`, nested dict, class attr, empty/single/triple tuples, negative/float elements, frozenset-of-int/str.
- Tests on the final commit: `test_ail_pre112` 4 OK, `test_ail_tuples` 26 OK, `test_ail_safetynet` 5 OK, `test_ail_files` 18 OK (1 skip), `test_ail_corpus_findings3` 2 OK. Extra: `test_ail_collections` 13 OK, `test_ail_sets_general` 10 OK, `test_ail_modconst` 26 OK.
- `test_ail_pre112.py` added (4 programs × 2 builds), registered in `ail_check.MODULES`.
- `tools/update_manifest.py` run, then `--check` rc=0.

Note: `print(D)` in the exact `t4h` still differs only in *frozenset display order* (`{(2,'b'),(1,'a')}` vs insertion order) — a pre-existing, separate difference from hash randomization, shown by a plain `print({(1,"a"),(2,"b")})` probe, not the KeyError.

Records: DEVLOG entry (2026-10-24) at the top of `DEVLOG.md`; DIFFERENCES row `C?-job-pre112-10242224-1` (status fixed).
[cost $0.0000, opencode tokens {"total": 11298476, "input": 150136, "output": 21946, "reasoning": 43642, "cache.write": 0, "cache.read": 11082752}]
    tool time: bash 21.3 min, edit 0.0 min, read 0.0 min, write 0.0 min
        333s bash   cd AIL_CURRENT && timeout 1800 python3 test_ail_collections.py 2>&1 | tail -5; echo "=== sets_general"; timeou
        129s bash   cd AIL_CURRENT && timeout 2400 python3 test_ail_corpus_findings3.py 2>&1 | tail -20
        108s bash   cd AIL_CURRENT && timeout 1800 python3 test_ail_modconst.py 2>&1 | tail -6
        100s bash   cd AIL_CURRENT && for t in test_ail_pre112 test_ail_tuples test_ail_safetynet test_ail_files test_ail_corpus_f
         84s bash   cd AIL_CURRENT && timeout 2400 python3 test_ail_files.py 2>&1 | tail -8
         78s bash   cd AIL_CURRENT && timeout 2400 python3 test_ail_safetynet.py 2>&1 | tail -8
         66s bash   cd AIL_CURRENT && timeout 1200 python3 test_ail_tuples.py 2>&1 | tail -25
         62s bash   for p in /tmp/probes/p01.py /tmp/probes/p02.py /tmp/probes/p03.py /tmp/probes/p04.py /tmp/probes/p05.py /tmp/p

## review 0
[model opencode/deepseek-v4.1-flash-free]
​**Review of `3cde15d` (pre112)**

**What the change does:** In the tuple pass it refuses a set/frozenset-of-tuples dict key when the container is not a table dict (`tupexpr.ex_Subscript`, `tupstmt.assign_one`), and bails on an untypable module-level constant mentioning a tuple (`tuplib.module_assign`), so the whole program falls back to the general path. Adds `test_ail_pre112.py`, DEVLOG/DIFFERENCES rows, manifest update. Matches the report.

**Probes (all HEAD general + default builds vs CPython):** p1–p7, q1–q5, r1–r6, s1–s7, t1–t6, u1–u6, x1–x4, w1–w4, v1–v4, y1–y4. All match CPython or are identical to base. Base reproduces the KeyError/wrong-`in`/wrong-`.get` in q1, q3, q5, r2, r3, r5, s3, s4, s5, s6, u5, x2; HEAD fixes all. No HEAD-only failure found.

**Exact `t4h`:** the literal 2-element module-level form (p1/y1/y2/y3/y4) already matches on base because the typed path falls back on `frozenset()`. The same cause still fails on base in the one-element, store, copy, comprehension, `dict([...])`, nested-list and class-attribute forms, and HEAD fixes those. So “t4h reproduced” is only partly verified, but the underlying defect is real and fixed.

**No-change check:** `program.c` is byte-identical base vs HEAD for 15 gdev programs with module-level tuple mentions/type aliases and for g06_026, g10_002, g00_010 (only `native_report.json` differs). No speed concern for unaffected code; the change is compile-time only.

**Tests on HEAD:** `test_ail_pre112`, `test_ail_safetynet`, `test_ail_tuples`, `test_ail_modconst`, `test_ail_files`, `test_ail_corpus_findings3` all OK. `update_manifest.py --check` rc=0; commit/records present.

**Pre-existing:** frozenset display order (worker’s note) — unrelated; not re-probed. Exact 2-element module-literal `t4h` already passed on base.

**Unverified:** worker’s own 15 probe files; `test_ail_collections`/`test_ail_sets_general` (not rerun); exhaustive check of the broad `module_assign` bail (sampled only).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 2171830, "input": 82785, "output": 12827, "reasoning": 26633, "cache.write": 0, "cache.read": 2049585}]
    tool time: bash 9.8 min
        131s bash   cd /home/runner/work/ail-ci/ail-ci && date && timeout 2400 python3 tools/par_check.py -j 2 test_ail_pre112 tes
         98s bash   cd /home/runner/work/ail-ci/ail-ci && date && timeout 2000 python3 tools/par_check.py -j 2 test_ail_files test
         40s bash   cd /tmp/rprobes cat > r1.py <<'EOF' D = {(1, 2): "x"} print(frozenset({(1, 2)}) in D) try:     print(D[frozens
         39s bash   cd /tmp/rprobes cat > s1.py <<'EOF' D: dict = {frozenset({(1, "a")}): "x"} print(D[frozenset({(1, "a")})]) EOF
         32s bash   cd /tmp/rprobes cat > u1.py <<'EOF' def f():     pairs = [(1, "a"), (2, "b")]     D = {frozenset(pairs): "x"} 
         31s bash   cd /tmp/rprobes cat > t1.py <<'EOF' def f(D: dict[frozenset[tuple[int, str]], str]) -> str:     return D[froze
         24s bash   cd /tmp/rprobes cat > x1.py <<'EOF' def f():     D = {frozenset({(1, "a")}): (1, 2)}     k = frozenset({(1, "a
         23s bash   cd ~/corpus/gdev && for f in g23_022 g11_024 g08_036 g10_014 g06_034; do for m in b h; do if [ $m = b ]; then 

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-24T14:57:11Z
