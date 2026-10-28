# job job-pre420-10281637  started 2026-10-28T07:38:02Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> uests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You have reached the daily usage limit. Please try again later."],"error_code":110,"fast_mode_state":"off","uuid":"24958174-592b-4ce7-8fe1-cf61a6ada86a","session_id":"c47dab2d-67e5-4397-b7f1-363f5b1524cb"}
DeepSeek-Flash -> l_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your daily usage limit for Chat. Come back tomorrow to continue working with me. Report Issue (input /feedback)"],"error_code":110,"fast_mode_state":"off","uuid":"5dc03c9e-b290-4144-9aac-cbc41b30f2bc","session_id":"d26151c7-83d9-4ee3-9c01-59a307d1dc5b"}

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Fixed and committed as `d963e77`.

**Cause:** general-path list/tuple index error used `ail_type_name(key.tag)` → `not instance`; now `ail__tname_c(key)` plus a 200-char-capped dynamic buffer (the old 96-byte buffer also truncated long names).

**Probes** (`cmp.sh`, both builds):
- `p2.py` — reported case: list/tuple now match; only the instance `KeyError` repr address differs (unmatchable, documented)
- `p2b.py` — argument/list-item/attribute/dict-value/subclass routes: match
- `p2c.py` — `__index__` instance and float/None/str keys: match
- `p2d.py` — empty list/tuple, names under 200 chars: match
- `p2e.py` — 210-char class name (capped like `%.200s`), exception-instance key: match
- `p2f.py` — non-int `__index__` return still says `not float` vs CPython's `__index__ returned non-int (type float)`; separate pre-existing cause, unchanged (not claimed fixed)

**Tests on final commit:** `test_ail_pre420`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 26 run, OK, 1 skipped (no zig). `update_manifest.py` run; `--check` passes.

## review 0
[model commandcode/deepseek-v4.1-flash]
**Change under review** — `d963e77` (`git diff work..HEAD`): in the general-path `ail_op_getitem`, the list/tuple "indices must be integers or slices" text now names the key with `ail__tname_c(key)` instead of `ail_type_name(key.tag)`, formatted into a 200-byte-capped `tnbuf` and a heap buffer sized from `sizeof(prefix)+strlen` (the old stack buffer and tag name are gone). Plus `test_ail_pre420.py`, registration in `ail_check.MODULES`, DEVLOG/DIFFERENCES/MANIFEST.

**What the change really does** — one line, matching the report's description. `ail__tname_c` already existed directly above (line 14814) and is copied into `tnbuf` before padding, so the static name buffer cannot alias; `ail_raise_c` copies the string (`ail_str_from_cstr`), so `free(buf)` after the raise is safe and leak-free.

**My probes** (`/tmp/rprobes`, `cmp.sh`, HEAD = this worktree; base = `git worktree add /tmp/base work`):

| probe | content | HEAD g/d | base |
|---|---|---|---|
| p1 | instance/subclass via argument, list item, attribute, dict value; list/tuple/empty | match | differs (`not instance`) |
| p2 | class object, `len`, lambda, dict, set, frozenset, range, iterator, None, float, str | only `iterator` vs `list_iterator` | same one, plus `function` vs `builtin_function_or_method` |
| p3 | class-name lengths 199/200/201/205 (the `%.200s` boundary) | match (lengths/truncation exact) | differs (`not instance`) |
| p4 | `__index__` returning int / 1.5 / raising | only the non-int case differs | identical to HEAD |
| p5 | no-feature program | match | – |
| p6 | 4000 raises alternating short and >80-char names (buffer reuse) | match, no crash | differs |
| p7 | non-ASCII class name | refused by name ("non-ASCII character in a string literal") | same refusal |
| p8/p9 | exception-instance key (user subclass) matches; `object()`, `Exception()`, dict view kept in a name refused by name | match / refused | same |
| p10 | subscript inside functions and a comprehension | match | – |
| p11 | exception instance, subclass instance, class attribute routes | match | – |

`p5` debug-dir vs base: `program.c` differs only in the changed runtime hunk — no emitted code changed; the runtime is embedded in every program, so that is inherent.

**Pre-existing** (identical on base, not blocking): `iterator` instead of `list_iterator` (p2); non-int `__index__` result says `list indices ... not float` instead of `__index__ returned non-int (type float)` (p4); `KeyError` repr `<C object>` vs `<__main__.C object at 0x...>` (worker p2); named refusals for non-ASCII names, `object()`/`Exception()` as values and dict views kept in a name.

**Tests on HEAD:** `par_check.py -j 2 test_ail_pre420 test_ail_safetynet` → 2 modules, 0 failed (7.6s / 89.9s). `update_manifest.py --check` → exit 0.

**Report claims:** fixed cause — verified; routes (argument/list item/attribute/dict/subclass) — verified (p1/p10/p11); `__index__`/float/None/str keys — verified; 210-char name cap — verified (p3, 205); non-int `__index__` unchanged — verified (p4 base = HEAD); worker p2/p2e/p2f — re-ran, claims hold. Not verified: the `test_ail_files` / `test_ail_corpus_findings3` runs (outside the reviewer's module set). Minor inaccuracy: "the old 96-byte buffer also truncated long names" — with `ail_type_name` the old name could never exceed 8 chars; harmless. Cosmetic: DEVLOG entry lacks a blank line before the next `##`.

**Speed:** not measured; the edited lines are inside the `key.tag != INT/BOOL` branch, so the int-index path (and every program that never raises this error) executes unchanged code.

VERDICT: ACCEPT

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-28T11:44:47Z
