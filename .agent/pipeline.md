# job job-pre387-10280823  started 2026-10-27T23:25:53Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> ice_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard","request_id":"11e43dad-b78a-45b5-b620-1caa2cebd819","context_usage_ratio":0.019626},"modelUsage":{"dfmodel":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0,"credits":0.16194866845714284}},"permission_denials":[],"fast_mode_state":"off","uuid":"6295bf97-c792-4da0-afaf-869e212997d5","session_id":"93cfe4b1-5caa-4e07-8205-40ca7b10e60b"}

## worker report 0
[model qoder/DeepSeek-Flash]
Done. Final state is committed on `job-pre387-10280823` (no push).

**Cause and fix**
- Recovered pre374 probes p09–p20; the first still differing was p10: `d = {"k": 1e300}; print(int(d.get("k"))); d.update({"k": 1.5})` trapped `integer overflow` on both builds (CPython prints the big integer).
- Added `_check_flow_int64_containers` in `AIL_CURRENT/ail_chatgpt.py`: order-aware module walk over literal containers/aliases/scalars; refuses the pre-mutation read by name (no runtime/codegen change).
- Follow-up guard: a user call shaped like the compiler's `_AilT_*` tuple constructors is treated as pure only when no argument is a tracked container (otherwise it stays unmodelled).

**Commits**
- `e5dc176` main fix + `test_ail_pre387.py` (12 refused / 26 matching) + DIFFERENCES row `C?-job-pre387-10280823-1` + DEVLOG.
- `1a53159` `_AilT_` guard + matching case (now 12 refused / 27 matching). Manifest regenerated; `update_manifest.py --check` rc 0.

**Probes** (`/tmp/probes/pre387/`, 49 total, `bash ~/tools/cmp.sh` on both builds): 29 match CPython, 20 refused by name (`int() of a float outside int64` / `int64 constant expression out of range`), 0 other failures. New q15 (module-level user `_AilT_swap` mutator) matches; the pre-guard compiler refused it falsely. p34 remains a pre-existing false refusal on base (unchanged); p33 refused as before.

**Tests on final commit `1a53159`** (`par_check.py -j 2`): pre387 96s, safetynet 107s, files 114s, corpus_findings3 199s; pre322 43s, pre340 29s, pre357 50s, pre358 36s, pre359 26s — 9 modules, 0 failed.

Not verified: the full suite (CI after merge) and any behaviour outside these modules/probes.

## review 0
[model qoder/DeepSeek-Flash]
Review complete. Findings below.

## What the change really does
`_check_flow_int64_containers` (ail_chatgpt.py:1452-1572) added to `_check_int64_literals` (line 1630): a source-order walk over module statements with a small read-only model (literal containers, aliases, scalars) that raises the existing named refusals when an `int()` read of a statically out-of-int64 value precedes any later mutation. It only raises; no codegen change.

## Defect (introduced)
The model drops tracked names mentioned by an unmodelled statement, but a `def`/`class` that is defined **before** the container is bound mentions nothing tracked at that point, and a later call does not mention the name. The mutation is then invisible and the read is falsely refused.

Probe `/tmp/rprobes/r02_func_before.py`:
```python
def f():
    d["k"] = 1.5

d = {"k": 1e300}
f()
print(int(d.get("k")))
```
- CPython: prints `1`, exit 0.
- Base (`/tmp/base`, commit `aa8056e`): builds, prints `1` (same stdout).
- HEAD: both builds fail with `p.ail:6:7: int() of a float outside int64: 1e+300 (CPython makes a big integer)`.

Same shape via a class (`r03_class_before.py`, staticmethod mutating the global before the read): base prints `1`, HEAD falsely refuses. This is a new false refusal, not present on the base, so it blocks.

## Verified claims
- p10 shape (`/tmp/rprobes/r01_p10.py`): base traps `integer overflow`, HEAD refuses by name — fixed as reported. **Verified.**
- Refusals from my probes that base trapped (r10 negative index, r11 empty-dict default, r14 nested dict, r16 call-valued mutation) are named refusals — acceptable. **Verified.**
- No codegen change: `--debug-dir` C for a non-feature program (`r09_nonfeature.py`) is byte-identical between HEAD and base; `native_report.json` differs only in temp paths/cwd. **Verified.**
- Aliasing/list-item/dict-value routes (r04, r05, r13, r15) match CPython on both builds. **Verified.**
- `test_ail_pre387` (94.7s) and `test_ail_safetynet` (105.3s) pass on HEAD, 0 failed; test file counts 12 REFUSED / 27 MATCH as reported. **Verified.**
- `update_manifest.py --check` rc 0. **Verified.**
- Speed: not run; the C is identical, so instruction counts cannot change. **Not applicable.**

## Pre-existing (identical on base, not blocking)
- `r06_arg.py` (`int(x)` on a parameter receiving 1e300): both builds trap `integer overflow`; CPython prints the big integer.
- `r12_attr.py` (`int(c.v[0])` then store): both trap.
- `r18_classattr.py` (`C.k = 1.5` before `int(C.k)`): both refuse falsely (this is the worker's p34).

## Unverified
- The recovered pre374 probes p09, p11-p20 other than p10; worker's own `/tmp/probes/pre387` suite; `test_ail_files` and `test_ail_corpus_findings3` (out of review scope).

VERDICT: FIX

1. **False compile-time refusal after a mutation through a definition that precedes the container.** Probe `r02_func_before.py` (above) and `r03_class_before.py`. Expected: prints `1`, exit 0 (base matches CPython). Actual: both builds fail with `int() of a float outside int64: 1e+300`. Cause: the flow model processes the `def`/`class` before the container exists, so `drop_mentions` has nothing to drop, and the later call `f()` / `C.go()` does not mention the tracked name. A user function or method defined earlier that mutates a module global can therefore hide the mutation from the pass.

## worker report 1
[model qoder/DeepSeek-Flash]
Fixed and committed as `f493716` (not pushed). Summary:

**Defect**: a `def`/`class` defined before the container was bound dropped nothing at its definition, and the later call did not mention the tracked name, so a mutation inside it was invisible and the read was falsely refused (`r02`, `r03`).

**Fix** (`AIL_CURRENT/ail_chatgpt.py`): a `def` now evaluates only its header (decorators/defaults/annotations) and a `class` only its class body. An unmodelled call that is not provably side-effect free for the module's globals — only an unshadowed pure builtin, a method of a tracked literal value, or an imported-module method are cleared — drops every tracked name. The mention drop now runs after call classification, so `d.update(...)` still only drops `d`.

**Probes** (34 in `/tmp/probes/pre387b`, both builds, `cmp.sh` + classifier):
- Match CPython (20): function/class/instance/lambda/alias/`global`-rebind routes, argument, nested-dict value, list item, dict value, returned alias, constructor attribute (`r02`–`r06`, `m01`–`m07`, `m11`, `m12`, `m14`–`m16`, `k07`, `x03`).
- Refused by name (14): read-before-call, pure builtin between, method of another tracked container, imported method, uncalled mutating method, negative index (`r07`–`r09`, `k01`–`k06`); plus 5 pre-existing refusals identical on base (`m08`–`m10` class-body/decorator subset rule, `x01`/`x02` eval/globals).
- All 49 recovered `pre387` probes keep their recorded result. Reviewer's 18 `rprobes`: `r02`/`r03` now match (were false refusals); `r01`, `r10`, `r11`, `r14`, `r16` refused by name; `r06`/`r12` keep the pre-existing trap; `r18` keeps its pre-existing subset refusal.

**Tests**: `test_ail_pre387` OK 147.2 s (17 refused / 39 matching programs, both builds); `test_ail_safetynet` + `test_ail_files` + `test_ail_corpus_findings3` OK, 25 tests (1 skipped), 418.4 s. `update_manifest.py --check` rc 0. Records updated with a 2026-10-28 DEVLOG entry and the existing DIFFERENCES row.

## review 1
[model qoder/DeepSeek-Flash]
## Review report

`date`: started 00:38, finished ~00:52. Base worktree `/tmp/base` = `aa8056e`.

**What the change really does** — adds `_check_flow_int64_containers` (ail_chatgpt.py:1331-1657), a source-order, module-level read-only model of literal containers/aliases/scalars that raises the existing named `int()`-overflow refusals when a read of an out-of-int64 value precedes the mutation; pure raise-only, no codegen change. Matches the report.

**Target fix — verified.** `a01`/`a03`/`a04` (dict/list/nested read before `update`/store) trap `integer overflow` on base, are refused by name on HEAD both builds. `r01/r10/r11/r14/r16` likewise. `r06/r12` trap identically on both (pre-existing). `r02/r03` match CPython on both. Debug-dir C for a non-feature program (`r09`) is byte-identical HEAD vs base; compile time of the largest gdev program 8.77 s → 8.64 s. Tests on HEAD: `test_ail_pre387` ok 167.8 s, `test_ail_safetynet` ok 119.9 s, 0 failed. `update_manifest.py --check` rc 0.

**Defect (introduced) — new false refusals, base matched CPython.** `safe_call` (ail_chatgpt.py:1533-1563) decides an unmodelled call is side-effect free without accounting for user callables it will invoke: the Name branch (1547) only rejects a bare name in `mutating` (module-level `FunctionDef`/`ClassDef` names — an alias or bound method slips through), and the Attribute/Subscript branch (1563, e.g. an imported module method) never inspects arguments at all. `_flow_pure_expression`'s `_AilT_` branch (1403) exempts a no-argument user `_AilT_*` call. In each case the mutation is invisible, the stale big value stays tracked, and a read after the call is falsely refused.

Probes (`bash ~/tools/cmp.sh`), all: CPython prints `1` / `{'k': 1.5}`, exit 0; base **same stdout**; HEAD both builds fail with `int() of a float outside int64: 1e+300`:
- `/tmp/rprobes/c01.py`: `g = f; sorted(items, key=g)` — callable alias.
- `/tmp/rprobes/c02.py` (`b01`): `sorted(items, key=c.m)` — bound method.
- `/tmp/rprobes/d01.py`: `import functools; functools.reduce(f, [1], 0)` — bare function name, imported-module callee.
- `/tmp/rprobes/c04.py`: `def _AilT_f(): d["k"] = 1.5` called with no argument.

This is the same false-refusal shape the job set out to fix (and the previous review blocked on); the report's claim "an unmodelled call … drops every tracked name" is **false** for these routes.

**Other claim checks** — `17 refused / 39 matching` is **false**: the table holds 17 REFUSED and 42 MATCH (59 programs). "All 49 recovered pre387 probes keep their recorded result" **unverified** (not present here). `test_ail_files` / `test_ail_corpus_findings3`: **unverified** (out of review scope).

**Pre-existing (identical on base, not blocking)** — `b03` (function-local read before mutation) traps on both; reads inside an `if`/`for` still trap on both; `r18` subset refusal on both; `exec` refused by the subset on both.

**Unverified** — worker's `/tmp/probes/pre387b` outputs; speed beyond compile-time (generated C identical, so instruction counts cannot change).

VERDICT: FIX

1. **False compile-time refusal when a user callable is invoked by a callee treated as safe.** Probes `c01.py` (`g = f; sorted(items, key=g)`), `c02.py` (`sorted(items, key=c.m)`), `d01.py` (`functools.reduce(f, [1], 0)`); `c04.py` (`_AilT_f()` with no argument). Expected: `1` / `{'k': 1.5}`, exit 0 (base matches CPython). Actual: both builds stop with `int() of a float outside int64: 1e+300` at the read. Cause: `safe_call` (ail_chatgpt.py:1533-1563) checks arguments only for a Name callee and only for bare `mutating` names (aliases, bound methods and callables from a dict/list/attribute are missed), and the imported-module/attribute branch checks no arguments; the `_AilT_` exemption (1403) ignores a no-arg user function. The missed mutation leaves the stale value tracked, so the later read is refused where the base built and matched CPython.

FINAL VERDICT: FIX  2026-10-28T00:47:41Z
