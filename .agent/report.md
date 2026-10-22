# job job-fuzz18-10221632  started 2026-10-22T07:32:52Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Committed `f30a9db` on `job-fuzz18-10221632`. No push.

**Fixes**
- `math.floor`/`math.ceil` now call `__floor__`/`__ceil__` and return the dunder result unchanged; fallback is `__float__`/`__index__` only when absent. A never-instantiated `_AilMathStub` keeps the call resolvable on the general path; `__floor__`/`__ceil__` are accepted dunders for the typed path.
- `_ail_math_checknum` rejects `type`/`function` by name before `hasattr`, so math helpers raise `TypeError must be real number, not type|function`.

**Probes (both builds, `cmp.sh`, same stdout as CPython)**
- `floorceil_dunder.py`, `floorceil_deep.py`, `floorceil_edge.py` — direct/arg/attr/list/dict/alias, dunder-only/float-only/index-only, non-int dunder results, raising dunders, big ints, inf/NaN, wrong types.
- `classtype.py`, `checknum_types.py` — class/function through sin/sqrt/fsum/floor/ceil/copysign/pow/isnan/fabs, direct/arg/list/dict; numeric objects still convert.
- `dundercall.py`, `stub.py` — dunder call and stub path.
- Residual (documented row `C?-job-fuzz18-10221632-3`): builtin function prints `not function` (CPython `builtin_function_or_method`); iterator still leaks `NotImplementedError`.

**Tests on final commit**
- `test_ail_fuzz18` (7), `test_ail_safetynet` (5), `test_ail_files` (18, 1 skipped), `test_ail_corpus_findings3` (2): OK
- Targeted `test_ail_python_syntax`, `test_ail_clock`, `test_ail_modules`, `test_ail_stdlib5` (114 total): OK
- `tools/update_manifest.py --check`: exit 0.
[cost $0.0000, opencode tokens {"total": 11220822, "input": 516108, "output": 54432, "reasoning": 12970, "cache.write": 0, "cache.read": 10637312}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review report

**Diff:** `math.floor`/`ceil` now dispatch `__floor__`/`__ceil__`, a `_AilMathStub` keeps the dunder call resolvable, and `checknum` rejects names `type`/`function`. `__floor__`/`__ceil__` added to accepted dunders on the typed path.

**Probes (both builds unless noted)**
- Intended fix works: `/tmp/rprobes/floorceil_dunder.py`, worker's `floorceil_deep.py`, `floorceil_edge.py`, `checknum_types.py`, plus `fc_inherit.py`, `fc_types2.py` — same stdout as CPython on both paths.
- No-feature C unchanged: `nofeat.py` built with `--debug-dir` on HEAD; `program.c` byte-identical to base.
- Regression found: `/tmp/rprobes/fc_function_name_min.py`.

```python
import math
class function:
    def __float__(self):
        return 1.5
print(math.sin(function()))
```
Expected CPython: `0.9974949866040544` (exit 0). Actual HEAD, both builds: `TypeError: must be real number, not function`, exit 1. Base matches CPython. The new name-based check rejects any user value whose class happens to be named `function` even though it is a normal numeric-convertible instance. Same wrong rejection for `math.floor`/`ceil` when such a class defines `__floor__`/`__ceil__`.

**Pre-existing differences (also wrong on base, different message)**
- Instance-level `__floor__`/`__ceil__`/`__float__` attributes: HEAD gives `AttributeError`, base gives `TypeError float()...`, CPython ignores instance attrs (`/tmp/rprobes/fc_instattr.py`).
- Class-level non-callable `__floor__` (`= None`, `= 5`): both builds wrong, HEAD `AttributeError`, base other TypeError (`/tmp/rprobes/fc_misc.py`).
- Builtin-function/iterator type names (`not function` vs `builtin_function_or_method`) and iterator `NotImplementedError` leak: as documented in `C?-job-fuzz18-10221632-3`.

**Claims**
- Dunder dispatch + unchanged result, fallback to `__float__`/`__index__`: verified.
- `type`/`function` values rejected by name: verified, but the name test also rejects legal user classes (defect above).
- Residual builtin/iterator differences documented: verified.
- Test claims: `test_ail_fuzz18`, `test_ail_safetynet` pass on HEAD; `test_ail_files`, `test_ail_corpus_findings3` pass (I did not re-run the other listed modules). Manifest `--check` not re-run.
- Speed: unverified; `perf_event_open` is denied here. Only `g03_016.py` in gdev uses floor/ceil (3 calls), so impact is negligible.

VERDICT: FIX
1. `_NONNUM_TYPE_NAMES` matches `type(x).__name__`, so a legal user class named `function` (with `__float__` or `__floor__`) is wrongly rejected. Probe `/tmp/rprobes/fc_function_name_min.py`; expected `0.9974949866040544`, actual `TypeError: must be real number, not function` (base prints the correct result). Match the actual class/function value rather than the type's name.
[cost $0.0000, opencode tokens {"total": 1235076, "input": 94249, "output": 7508, "reasoning": 11271, "cache.write": 0, "cache.read": 1122048}]

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Committed `53e8bb4` on `job-fuzz18-10221632`.

Fix: removed `type`/`function` from the name-based reject list and made the general path answer `hasattr(x, "__float__"/"__index__"/"__floor__"/"__ceil__")` from program classes, so real class/function values still get CPython's `TypeError` while a user class named `function` converts normally.

Probes (both builds, all same stdout as CPython):
- `/tmp/rprobes/fc_function_name_min.py`, `floorceil_dunder.py`, `classtype.py`
- `/tmp/probes/fc_named_function.py` — named class with `__float__`/`__floor__`/`__ceil__`/`__call__`, `__index__`-only class, inner `__float__` TypeError, direct/arg/list/dict/attribute, plus real class/function rejection
- `/tmp/probes/checknum_types.py`, `floorceil_dunder.py`, `floorceil_edge.py`, `floorceil_deep.py`

Tests on final commit: `test_ail_fuzz18`, `test_ail_safetynet`, `test_ail_files` → 30 tests OK (1 skip); `test_ail_corpus_findings3`, `test_ail_gaps_api2`, `test_ail_grid_calls`, `test_ail_pathlib`, `test_ail_stdlib5` → 63 tests OK (1 skip). Manifest `--check` passes.

Docs updated: DEVLOG entry and DIFFERENCES row `C?-job-fuzz18-10221632-4`.
[cost $0.0000, opencode tokens {"total": 3263819, "input": 225541, "output": 11360, "reasoning": 17510, "cache.write": 0, "cache.read": 3009408}]

## review 1 failed to run: [model opencode/deepseek-v4.1-flash-free] (no final text) [cost $0.0000, opencode tokens {"total": 85384, "input": 9018, "output": 544, "reasoning": 1454, "cache.write": 0, "cache.read": 74368}] 

## review 1
[model opencode/deepseek-v4.1-flash-free]
(no final text)
[cost $0.0000, opencode tokens {"total": 513348, "input": 35549, "output": 4788, "reasoning": 8627, "cache.write": 0, "cache.read": 464384}]

FINAL VERDICT: ERROR  2026-10-22T09:35:15Z
