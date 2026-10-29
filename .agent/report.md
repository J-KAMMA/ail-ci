# job job-ex36-10291446  started 2026-10-29T05:48:34Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> ts":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["Your personal Credits have been exhausted. Please check your plan."],"error_code":118,"fast_mode_state":"off","uuid":"096d9503-0e7d-4ba8-87d4-2a3382604efa","session_id":"998facc4-b5a1-497a-a96b-546f47bfbd06"}
DeepSeek-Flash -> input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your credit usage limit. Please upgrade your subscription plan to get more resources. Report Issue (input /feedback)"],"error_code":118,"fast_mode_state":"off","uuid":"a371be8b-5000-49ec-aae8-2f16f169c3d3","session_id":"b5754427-e80e-481f-90f3-acb5f14124db"}

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Implemented and committed `fb13b9e` (`ex36: compile @export as the CPython identity decorator`).

- `@export` from `ail_ffi` now compiles as CPython’s identity decorator; `c_export/geometry.py` builds on both builds and matches CPython stdout/exit.
- Ported the reviewed `@export` checks, including unused-import typed-path preservation, future-annotation dataclass refusal, and rebinding refusal.
- Added `AIL_CURRENT/test_ail_ex36.py` and registered it in `ail_check.py`.
- Probes: 4 match CPython on both builds; 1 refused by name where CPython raises.
- Tests passed: `test_ail_ex36` + `test_ail_ffi` + `test_ail_c_export` + `test_ail_unified` (63), `test_ail_safetynet` (5), `test_ail_files` (18), `test_ail_corpus_findings3` (2).
- `tools/update_manifest.py --check` rc 0. Working tree clean except untracked `.agent/pipeline.md`.
[cost $0.0000, opencode tokens {"total": 8901044, "input": 284846, "output": 20219, "reasoning": 24715, "cache.write": 0, "cache.read": 8571264}]
    tool time: bash 30.5 min, edit 0.0 min, read 0.0 min, write 0.0 min
        766s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1800 python3 -m unittest -q test_ail_ex36 test_ail_f
        279s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 -m unittest -q test_ail_corpus_findings3
        250s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1800 python3 -m unittest -q test_ail_safetynet 2>&1 
        147s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 -m unittest -q test_ail_files 2>&1 | tai
        133s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 -m unittest -q test_ail_ex36 2>&1 | tail
         32s bash   mkdir -p /tmp/probes && cd /home/runner/work/ail-ci/ail-ci && cat >/tmp/probes/ex36_export_bare.py <<'PY' from
         31s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/ex36_export_bare.py /tmp/probes/ex36_export_call.py
         26s bash   cd /home/runner/work/ail-ci/ail-ci && PYTHONPATH="$PWD/AIL_CURRENT" bash ~/tools/cmp.sh AIL_CURRENT/language_e

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: `fb13b9e` ex36 `@export`

**What the diff really does:** makes `@export` (bare, `@export()`, or `mod.export`) a no-op identity in both emitters, adds CPython-mirroring annotation/rebinding checks in `pyboxed2`, keeps the `ail_ffi` import line only when the decorator is written, and adds a `future` marker for dataclasses. It changes both the general path and the default path (`pyboxed.py` too), not only the general path as the report implies.

**Verified claims:** commit and files; `geometry.py` builds on both builds and matches CPython (`g0_geometry`); the two examples that build (`geometry`, `table_crc`) and 12 refusals on HEAD; unused-import typed path (`p6`), future-dataclass/rebinding refusals (tests); manifest `--check` rc 0; tree clean apart from untracked `.agent/pipeline.md`; `test_ail_ex36`, `test_ail_ffi`, `test_ail_c_export`, `test_ail_unified`, `test_ail_safetynet` all pass.

**Defects (change-caused, silent):**

1. `@export` above `@lru_cache`/`@cache`. CPython passes the C wrapper to `export`, which raises `TypeError: @export applies to a top-level function`. On base both builds refused by name (acceptable); on HEAD both run and print.
```
from functools import lru_cache
from ail_ffi import export
@export
@lru_cache(maxsize=None)
def f(x: int) -> int: return x * x
print(f(3))
```
Expected: exit 1, no stdout, `TypeError: @export applies to a top-level function`.
Actual HEAD (g and d): exit 0, stdout `9`. (`@cache` behaves the same: `r4_export_outer_cache` prints `4`.)

2. `@export(...)` with arguments is silently treated as identity; CPython calls `export(<arg>)` and rejects it.
```
from ail_ffi import export
@export(123)
def f(x: int) -> int: return x
print(f(2))
```
Expected: exit 1, `TypeError: @export applies to a top-level function`.
Actual HEAD (g and d): exit 0, stdout `2`. Base general refused by name; base default already had this divergence.

3. Dataclass fields excluded from `__init__` are not checked. CPython inspects `dataclasses.fields`, so an `init=False` field of a disallowed type rejects the export; AIL only scans `__init__` parameters.
```
from dataclasses import dataclass, field
from ail_ffi import export
@dataclass
class P:
    x: int
    label: str = field(init=False, default="z")
@export
def f(p: P) -> int: return p.x
print(f(P(1)))
```
Expected: exit 1, `TypeError: @export f: parameter p needs ...`.
Actual HEAD (g and d): exit 0, stdout `1`. Base default already printed `1` (pre-existing); base general refused by name.

**Pre-existing (do not block):** for defects 2 and 3 the default build already diverged on `work`; `r3_forward_class_plain` (`def f(p: P)` before `class P`) also silently differs on both base and HEAD, independent of `@export`.

**Unverified:** `test_ail_files`, `test_ail_corpus_findings3` not rerun; no speed check (change is not on hot runtime code).

VERDICT: FIX
1. Refuse (or reproduce CPython's `TypeError` for) `@export` placed outermost over a decorator that yields a non-function such as `lru_cache`/`cache`; probe `r1_export_outer_lru.py`, expected exit 1/no stdout, actual exit 0/stdout `9`.
2. Refuse `@export(...)` calls that pass an argument/keyword; probe `q2_export_arg.py` (`@export(123)`), expected exit 1, actual exit 0/stdout `2`.
3. Validate every dataclass field, including `init=False`, not only `__init__` parameters; probe `q1_initfalse_str.py`, expected exit 1, actual exit 0/stdout `1` (and `q5_initfalse_bad_type.py` likewise).
[cost $0.0000, opencode tokens {"total": 1960445, "input": 140194, "output": 7448, "reasoning": 20931, "cache.write": 0, "cache.read": 1791872}]
    tool time: bash 15.0 min
        465s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date; timeout 1100 python3 ../tools/par_check.py -j 2 test_a
        154s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date; timeout 900 python3 ../tools/par_check.py -j 2 test_ai
         65s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/p*.py; do echo "===== $(basename $p)"; PYTHONPATH=
         42s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/q*.py; do echo "===== $(basename $p)"; PYTHONPATH=
         35s bash   cd /home/runner/work/ail-ci/ail-ci && for p in u1_future_dc u2_plain_dc u3_plain; do for mode in d g; do for t
         28s bash   cd /home/runner/work/ail-ci/ail-ci && date; export PYTHONPATH="$PWD/AIL_CURRENT"; for f in $(find AIL_CURRENT/
         25s bash   cd /tmp/rprobes cat > s1_mixed_import.py <<'PY' from ail_ffi import export, extern  @export def f(x: int) -> i
         25s bash   cd /home/runner/work/ail-ci/ail-ci && find AIL_CURRENT/language_examples -name '*.py'; echo ===; date; mkdir -

## worker report 1
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Fixed all three review defects and committed as `99c54bb`.

**Changes**
- `@export` above inner `@lru_cache`/`@cache` now refused by name (was exit 0 / printed).
- `@export(...)` with any positional/keyword argument now refused; `@export()` still identity.
- Dataclass export validation now checks every field, including `field(init=False)`; `ail_syntax` records merged field types in the `# ail:dataclass` marker and `pyboxed2` consumes them.
- Mirrored the decorator-application checks in the v1 emitter.
- Added the new boundaries to `test_ail_ex36.py`, plus DEVLOG and DIFFERENCES rows.

**Probes (all through `cmp.sh`, both g/d builds)**
- Match CPython: `p1_initfalse_ok`, `p3_initfalse_inherited_ok`, `p4_export_inside_cache`, `p5_export_empty_call`.
- Refused by name where CPython raises `TypeError`: `r1_export_outer_lru`, `r4_export_outer_cache`, `q2_export_arg`, `q1_initfalse_str`, `q5_initfalse_bad_type`, `p2_initfalse_inherited_bad`, `p6_export_kw_arg`, `p7_alias_outer_lru`, `p8_alias_arg`, `p9_initfalse_listint_bad`.

**Tests on final tree**
- `test_ail_ex36`, `test_ail_dunders`, `test_ail_python_syntax`, `test_ail_source_check`, `test_ail_builtin_syntax_forms`, `test_ail_ffi`, `test_ail_c_export`, `test_ail_unified`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: all pass (0 failed).
- `tools/update_manifest.py --check`: rc 0.
[cost $0.0443, opencode tokens {"total": 3987747, "input": 105350, "output": 13232, "reasoning": 14957, "cache.write": 0, "cache.read": 3854208}]
    tool time: bash 20.4 min, edit 0.0 min
        774s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 3000 python3 ../tools/par_check.py -j 2 test
        132s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 2400 python3 ../tools/par_check.py -j 2 test
        121s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1200 python3 ../tools/par_check.py -j 2 test
        115s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' from pathlib import Path p = Path('AIL_CURRENT/test_ail
         37s bash   cd /tmp/probes && cat > p1_initfalse_ok.py <<'PY' from dataclasses import dataclass, field from ail_ffi import
         18s bash   mkdir -p /tmp/probes && cd /tmp/probes && cat > r1_export_outer_lru.py <<'PY' from functools import lru_cache 
         14s bash   cd /home/runner/work/ail-ci/ail-ci && export PYTHONPATH="$PWD/AIL_CURRENT" && for p in r1_export_outer_lru r4_
          9s bash   cd /tmp && for p in q1_initfalse_str q2_export_arg r1_export_outer_lru; do echo "===== $p"; d=$(mktemp -d); cp

## review 1 skipped: only 10 minutes left

FINAL VERDICT: FIX  2026-10-29T10:33:11Z
