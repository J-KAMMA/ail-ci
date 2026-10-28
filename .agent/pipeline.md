# job job-pre402-10281051  started 2026-10-28T01:52:28Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> uests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You have reached the daily usage limit. Please try again later."],"error_code":110,"fast_mode_state":"off","uuid":"464f0b5f-fdb0-4f44-8e35-bcbbb0aea137","session_id":"bed75a94-2762-4189-9a0f-e3e4eeeddc72"}
DeepSeek-Flash -> l_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your daily usage limit for Chat. Come back tomorrow to continue working with me. Report Issue (input /feedback)"],"error_code":110,"fast_mode_state":"off","uuid":"ca215cff-3588-4cf0-8bd3-70182a24e9c6","session_id":"64471376-0539-4869-a063-00af9340c42f"}

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Commit `33c2c50` on `job-pre402-10281051`.

- The task's pre-existing list was missing (only “Unverified”); I recovered pre387's review and fixed its first item, `b03`: function-local container read before a later mutation trapped with `integer overflow` on both builds.
- Added a source-order scope flow pass in `AIL_CURRENT/ail_chatgpt.py:1346`, called from `_check_int64_literals`; it refuses the read by name before the mutation. Compile-time only, no codegen change.

Probes in `/tmp/probes/pre402` (both builds):
- Refused by name: `b03_local_list`, `b03_local_dict`, `b03_local_alias`, `r01_local_empty_default`, `r02_local_negative`, `r03_local_nested`, `r04_local_tuple`, `r05_local_del_after_read`, `r06_local_alias_chain`, `r07_local_dict_string` (10).
- Match CPython: `m01`–`m07` (mutation first list/dict/alias/method, in-range, int64 max, tuple rebind) (7).
- Exploratory `if_read`, `for_read`, `r18_classattr`, `exec_probe` remain pre-existing trap/subset refusal, unchanged.

Final-tree tests: `test_ail_pre402`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 349 s, 0 failed; related `test_ail_pre357/358/359/371` — 4 modules, 105 s, 0 failed. `update_manifest.py --check` passes.
[cost $0.0000, opencode tokens {"total": 5354131, "input": 116367, "output": 14949, "reasoning": 22559, "cache.write": 0, "cache.read": 5200256}]
    tool time: bash 9.8 min
        351s bash   cd AIL_CURRENT && timeout 2400 python3 ../tools/par_check.py -j 2 test_ail_pre402 test_ail_safetynet test_ail_
        107s bash   cd AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_pre357 test_ail_pre358 test_ail_pre
         32s bash   for p in /tmp/probes/pre402/[mr]*.py; do echo "===== $(basename $p)"; timeout 300 bash ~/tools/cmp.sh "$p" "$P
         31s bash   python3 - <<'PY' from pathlib import Path p = Path('AIL_CURRENT/test_ail_pre402.py') t = p.read_text() old = "
         28s bash   for p in /tmp/probes/pre402/*.py; do echo "===== $p"; timeout 300 bash ~/tools/cmp.sh "$p" "$PWD" 2>&1 | grep 
         25s bash   cd AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_pre402 2>&1 | tail -30
          3s bash   timeout 300 bash ~/tools/cmp.sh /tmp/probes/pre402/r04_local_tuple.py "$PWD" 2>&1 | tail -25
          3s bash   timeout 60 git fetch --no-tags origin 29d5e23be6f85df19eeb76c5e33154d84074cf92 2>&1 | tail -5; git log --oneli

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: pre402 (`33c2c50`)

**What the change really does** — Adds `_check_scope_flow_int64_containers`, called per `FunctionDef`/`AsyncFunctionDef` from `_check_int64_literals`: a source-order, function-local model of literal containers/aliases/scalars that raises the existing named `int()`-overflow refusals. Raise-only, no codegen change. This matches the report, except its claim that this pass "never invent[s]" a refusal.

**Defect (introduced) — false refusal when a mutator is invoked through a callback alias**

`/tmp/rprobes/r_e_sorted_alias.py`:
```python
def f():
    d = {"k": 1e300}
    def g(x):
        d["k"] = 1.5
        return x
    h = g
    sorted([1, 2], key=h)
    print(int(d.get("k")))
f()
```
CPython and base (`/tmp/base`): print `1`, exit 0. HEAD: both builds fail with `p.ail:8:11: int() of a float outside int64: 1e+300`.
Same with `/tmp/rprobes/r_d_builtin_map.py` (`h = g; list(map(h, [1, 2]))`): base prints `1`, HEAD falsely refuses.

Cause: `safe_call` deems `sorted`/`list`/`map` side-effect free because the argument `h` is not in the local `mutating` set (`mutating` holds `g`, not its alias). `drop_mentions` drops only `h`, so stale `d` is refused. This is the same false-refusal shape pre387's review blocked on (fixed there in `f493716`, which is not in this base).

Also `/tmp/rprobes/q2_dead_return.py` (statement after `return`): base matches CPython, HEAD refuses at compile time; `/tmp/rprobes/q1_uncalled_local.py` likewise. The pass has no reachability check.

**Claims**
- b03 list/dict/string shape: base traps, HEAD refuses by name on both builds — **verified** (`p01`, `p02`, `p03`).
- Mutation-first, in-range, int64 max, slice/walrus/del cases — **verified** (`p04`, `p06`, `p08`, `p09`, `p10`, `p11`).
- No codegen change — **verified**: `--debug-dir` `program.c` byte-identical HEAD vs base for `p12`; `native_report.json` differs only in temp paths.
- `test_ail_pre402` + `test_ail_safetynet` pass on HEAD (125 s, 0 failed) — **verified**. `update_manifest.py --check` rc 0 — **verified**.
- b03 is the first pre-existing item in pre387's review list — **verified** from the fetched pre387 review.
- Report: "any compound statement or unmodelled call drops the tracked names so it can cost a refusal but never invent one" — **false** (`r_d`, `r_e`, `q1`, `q2` invent refusals).

**Pre-existing (identical on base, not blocking)** — module-level `d = {"k": 1e300}; int(d.get("k")); d.update(...)` still traps on both HEAD and base; not the b03 item.

**Unverified** — worker's `/tmp/probes/pre402` files, `test_ail_files`/`test_ail_corpus_findings3`, speed (generated C identical).

VERDICT: FIX

1. **False compile-time refusal after a mutation hidden behind a callback alias.** Probe `r_e_sorted_alias.py` above (also `r_d_builtin_map.py`). Expected: `1`, exit 0 (base matches CPython). Actual: both builds fail with `int() of a float outside int64: 1e+300`. The callee `sorted`/`list`/`map` is treated as safe because the aliased mutator `h` is not in `mutating`, so the tracked container `d` is not dropped.
2. **False compile-time refusal of unexecuted/dead code.** Probe `q2_dead_return.py` (`items = [1e300]; return 0; print(int(items[0])); items[0] = 1.5`) and `q1_uncalled_local.py` (mutating function never called). Expected: CPython/base output `0` / `ok`, exit 0. Actual: HEAD refuses both builds with `int() of a float outside int64: 1e+300`.
[cost $0.0000, opencode tokens {"total": 1867709, "input": 80951, "output": 6972, "reasoning": 36682, "cache.write": 0, "cache.read": 1743104}]
    tool time: bash 3.8 min
        127s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_a
         28s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/p*.py; do echo "===== $(basename $p)"; timeout 300
         19s bash   cd /tmp/base && for p in p01_b03 p02_dict_get p03_bigstr p05_scalar p07_alias_rebind; do echo "===== $p"; time
         14s bash   cd /tmp/rprobes && cat > r_e_sorted_alias.py <<'EOF' def f():     d = {"k": 1e300}     def g(x):         d["k"
         10s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/r_*.py; do echo "===== $(basename $p) HEAD"; timeo
          9s bash   cd /tmp/rprobes && cat > r_mod_level.py <<'EOF' d = {"k": 1e300} print(int(d.get("k"))) d.update({"k": 1.5}) E
          7s bash   cd /tmp/base && for p in q1_uncalled_local q2_dead_return q3_uncalled_literal q4_dead_after_return q6_no_mutat
          5s bash   cd /home/runner/work/ail-ci/ail-ci && for p in r_e_sorted_alias r_f_direct_sorted; do echo "===== $p HEAD"; ti

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed both review defects and committed as `16453b9` (no push).

- Callback aliases/indirect callbacks now drop tracked containers; uncalled functions are skipped and bodies stop at `return`/`raise`.
- Probes `/tmp/probes/pre402fix` (15): 11 match CPython, 3 refused by int64 name, 1 by existing subset name; both builds.
- Final tests: `test_ail_pre402`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 290 s, 0 failed. `update_manifest.py --check` passes.
[cost $0.0000, opencode tokens {"total": 1529807, "input": 140575, "output": 8409, "reasoning": 23639, "cache.write": 0, "cache.read": 1357184}]
    tool time: bash 8.5 min
        292s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 1800 python3 tools/par_check.py -j 2 test_ail_pre402 test_ail_sa
         66s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 -X utf8 -B -m unittest -q test_ail_pre40
         51s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/pre402fix/f*.py; do echo "===== $(basename $p)"; ti
         51s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/pre402fix/f*.py; do echo "===== $(basename $p)"; ti
         32s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/q1_uncalled_local.py /tmp/rprobes/q2_dead_return.p
         13s bash   cd /tmp/probes/pre402fix && cat > f04_callback_list_item.py <<'EOF' def f():     d = {"k": 1e300}     def g(x)
          4s bash   cd /tmp/probes/pre402fix && cat > f06_callback_attribute.py <<'EOF' def f():     d = {"k": 1e300}     def g(x)
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' from pathlib import Path p = Path('AIL_CURRENT/ail_chat

## review 1
[model opencode/deepseek-v4.1-flash-free]
Reviewed `git diff work..HEAD` (2 commits). The change adds a compile-time-only AST pass in `ail_chatgpt.py` that tracks local literal containers/aliases/scalars in "reachable" functions and refuses out-of-int64 `int()` reads before a later mutation; it also drops tracked values for aliased/indirect callbacks and stops bodies at top-level `return`/`raise`. Generated C is unchanged for accepted programs (verified with `--debug-dir` on a plain program: only temp paths differ).

Verified:
- Original `b03`: base overflows at runtime; HEAD refuses by name on both builds (`int() of a float outside int64: 1e+300`).
- Worker probes `f01`–`f15`: 11 match CPython, 3 refused by int64 name, 1 existing subset refusal (`f06`) — claim confirmed.
- `test_ail_pre402` + `test_ail_safetynet`: 0 failed (125 s); `update_manifest.py --check` passes.
- Top-level `return`/`raise` dead code (`q2`, `f11`, `f12`): matches CPython.

False / defects:
1. Reachability is keyed by bare function name, so an uncalled nested function or method sharing a name with a called function is analysed and falsely refused. Claim "an uncalled nested function is not analysed" is false.
2. Calls in constant-dead branches count as reachable, so a call that never executes still triggers analysis/refusal.

Pre-existing (identical on base, non-blocking): indirect call `h = f; h()` still overflows; nested-class/attribute spellings remain subset/literal refusals.

```
def f(): print("called")
def g():
    def f():
        items = [1e300]
        print(int(items[0]))   # never runs
        items[0] = 1.5
    print("g")
f(); g()
```
Expected `called\ng`; actual HEAD (both builds) compile failure `p.ail:7:15: int() of a float outside int64: 1e+300`. Base matches CPython. Same for a method named like a called function.

```
def f():
    items = [1e300]
    print(int(items[0]))
    items[0] = 1.5
if False:
    f()
print("ok")
```
Expected `ok`; actual HEAD compile failure `p.ail:3:11: int() of a float outside int64: 1e+300`. Base matches CPython. Same with `while False:` and with the dead call inside a called function.

Time box: stopped probing at ~8 min; no source edits or commits made.

VERDICT: FIX
1. Name-keyed reachability conflates homonymous functions: an uncalled nested function/method (`/tmp/rprobes/c1_collision_nested.py`, `c2_collision_method.py`) is refused though CPython prints `called\ng` / `called\nok`; base compiles and matches.
2. Dead-branch calls mark functions reachable: `/tmp/rprobes/c4_if_false.py`, `c5_while_false.py`, `c10_dead_branch_caller.py` are refused at `int(items[0])` though the call never executes; CPython prints `ok`; base compiles and matches.
[cost $0.0000, opencode tokens {"total": 855237, "input": 46154, "output": 4444, "reasoning": 19359, "cache.write": 0, "cache.read": 785280}]
    tool time: bash 4.2 min
        127s bash   date; timeout 900 python3 tools/par_check.py -j 2 test_ail_pre402 test_ail_safetynet 2>&1 | tail -30; date
         52s bash   date; for p in /tmp/probes/pre402fix/f*.py; do out=$(timeout 120 bash ~/tools/cmp.sh "$p" "$PWD" 2>&1); echo "
         22s bash   date; for p in /tmp/rprobes/c1_collision_nested.py /tmp/rprobes/c2_collision_method.py /tmp/rprobes/c3_genexp_
         18s bash   date; for p in /tmp/rprobes/c*.py; do echo "===== $(basename $p)"; timeout 200 bash ~/tools/cmp.sh "$p" "$PWD"
         13s bash   date; for p in /tmp/rprobes/q5_conditional_dead.py /tmp/rprobes/q2_dead_return.py /tmp/rprobes/q4_dead_after_r
          7s bash   cat > /tmp/rprobes/a1_indirect_call.py <<'EOF' def f():     items = [1e300]     print(int(items[0]))     items
          5s bash   rm -rf /tmp/dbg_head /tmp/dbg_base cd /tmp/rprobes AIL_UNIFIED_FORCE=1 AIL_NO_CACHE=1 AIL_QUIET_FALLBACK=1 pyt
          4s bash   ls /tmp/probes/pre402fix /tmp/probes/pre402 2>/dev/null; echo ===; mkdir -p /tmp/rprobes; cat > /tmp/rprobes/b

FINAL VERDICT: FIX  2026-10-28T02:40:42Z
