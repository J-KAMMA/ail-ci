# job job-fuzz80-10231551  started 2026-10-23T06:52:15Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Committed `c857241` on `job-fuzz80-10231551`.

**Fixed:** empty `Enum`/`IntEnum`/`StrEnum`/`Flag`/`IntFlag` classes were silently built: `E(0)` produced a pseudo-member and `F(0)` succeeded, while CPython raises `TypeError` for an empty enum/flag. These classes are now refused by name at compile time on both builds (`enumlib.py:239`).

**Probes** (all `/tmp/probes`, both builds):
- Same as CPython: `p01_dict`, `p02_order`, `p03_lookup`, `p05_auto`, `p06_match`, `p14_zero_negative`, `p15_alias_only`.
- Refused by name: `p08_empty`, `p11_empty_method`, `p12_empty_flag_method`, `p13_underscore_member`.
- Other differences seen, not fixed: `p04` unary `+IntEnum` raises `TypeError`; `p16` (`p07` same cause) a `StrEnum` member works as a dict key but plain `"a"` lookup misses/`KeyError` despite equal hash/equality; `p09` huge int member values hit `integer overflow`; `p10` a nested enum class is refused.

**Tests on final commit:**
- `test_ail_fuzz80`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: 27 passed, 1 skipped (no zig for Windows), 478s.
- Enum-targeted `test_ail_stdlib5`, `test_ail_cov2`: 17 passed, 424s.
- `update_manifest.py --check`: rc 0.

No `DEVLOG`/`DIFFERENCES` files exist in this checkout, so no record rows were added.
[cost $0.0000, opencode tokens {"total": 2876812, "input": 374885, "output": 10747, "reasoning": 11308, "cache.write": 0, "cache.read": 2479872}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Change:** adds one compile-time refusal in `enumlib.py:240` when an enum class has no built members.

**Probes** (both builds; base = `/tmp/base`, HEAD = `$PWD`):

| probe | CPython / base | HEAD |
|---|---|---|
| `r1_empty_base.py`: empty `Enum` base with methods, subclassed with members | `x [<A.X: 1>, <A.Y: 2>] 2`; base both builds same | both builds fail to compile: `enum class Base has no members ...` |
| `r2_empty_base_pass.py`: empty `Enum` base, subclassed | `[<A.X: 1>] 1`; base both builds same | both builds fail to compile |
| `r3_empty_use.py`: empty enum only `list/len/__members__` | `[] 0 {}`; base both builds same | both builds fail to compile |
| `r4_underscore_member.py`: `_X = 1` | base wrong (`AttributeError`, pre-existing) | refused by name |
| `r5_multitarget.py`: `A = B = 1` | base compile refusal (pre-existing) | refused by name |
| `r9_empty_flag_only.py`: empty Flag/IntFlag called with 0 | base prints `<F: 0>` / `<G: 0>` (the real silent bug) | refused by name |
| `r10_empty_intenum_call.py`: empty E/I/S called with 0 | base prints `ValueError 0 is not a valid E` (not a pseudo-member) | refused by name |
| `r7_str_enum_key.py`: StrEnum key vs plain `"a"` | base/HEAD `KeyError 'a'`, CPython `1` (pre-existing, reported) | same |

Corpus regression: `corpus/gdev/g25_028.py` uses `class LinearUnit(Enum)` (methods only) as a base for `Length`/`Mass`. On base both builds exit 0 and match CPython; on HEAD both builds fail at line 6 with `enum class LinearUnit has no members this compiler builds ...`.

**Tests:** `test_ail_fuzz80` and `test_ail_safetynet` pass on HEAD (`-j 2`); `update_manifest.py --check` rc 0.

**Claim check:**
- Commit `c857241`: verified.
- Empty enums now refused by name on both builds: verified.
- "`E(0)` produced a pseudo-member": **false** — empty Enum/IntEnum/StrEnum raised `ValueError`, not a pseudo-member; only empty Flag/IntFlag returned `<F: 0>`.
- "`F(0)` succeeded": verified.
- `p01`–`p16` probes: unverified (not present); `p16` StrEnum dict-key difference independently verified.
- Test/coverage counts besides the two modules I re-ran: unverified.
- No DEVLOG/DIFFERENCES files: verified.

**Defects:**
1. The refusal is attached to the class definition, so it rejects valid empty enum classes that are never called. Specifically, an empty enum used as an abstract base (with methods) and extended by a non-empty enum no longer compiles, although it compiled correctly before this change (probe `r1_empty_base.py`: expected `x [<A.X: 1>, <A.Y: 2>] 2`, actual compile error on both builds; same for `r2_empty_base_pass.py` and `corpus/gdev/g25_028.py`). The refusal should be limited to the operation that was actually wrong (e.g. calling a memberless enum), not the valid base-class definition.

VERDICT: FIX
[cost $0.0000, opencode tokens {"total": 731990, "input": 63717, "output": 5923, "reasoning": 11982, "cache.write": 0, "cache.read": 650368}]

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Committed `34a477b` on `job-fuzz80-10231551`.

**Fix:** moved the empty-enum refusal from the class definition to the call site (`enumlib.py` `Uses.visit_Call`). Empty enums now compile, iterate, and work as base classes; only calling a memberless enum is refused by name. Corpus `g25_028.py` matches CPython again.

**Probes** (`bash ~/tools/cmp.sh`, both builds):
- Match CPython: `p01_empty_use_enum`, `p02_empty_use_flag`, `p03_empty_base`, `p04_empty_base_prop`, `p08_empty_base_pass`, `p09_empty_base_empty_child`, `p10_nonempty_checks`, `p11_empty_chain`, `corpus/gdev/g25_028.py`.
- Refused by name on both builds, CPython raises TypeError: direct `E(0)` for all five kinds, plus calls in a list/dict value (`p05`), through an attribute (`p06`), and through an argument (`p07`).

**Tests on final commit:** `test_ail_fuzz80` 4, `test_ail_safetynet` 5, `test_ail_files` 18 (1 skip), `test_ail_corpus_findings3` 2, `test_ail_stdlib5` 10, `test_ail_cov2` 7 — all OK. `update_manifest.py --check` rc 0. No DEVLOG/DIFFERENCES files exist in this checkout.
[cost $0.0000, opencode tokens {"total": 1317213, "input": 95054, "output": 6650, "reasoning": 9237, "cache.write": 0, "cache.read": 1206272}]

## review 1
[model opencode/deepseek-v4.1-flash-free]
**Review: `work..HEAD` (c857241, 34a477b)**

**Change:** only `enumlib.py` `Uses.visit_Call` now refuses direct calls to enums with no members/aliases; empty enums still compile, iterate and act as bases. Plus `test_ail_fuzz80.py`, `ail_check.py`, `MANIFEST.json`.

**Probes (HEAD, both general/default builds; compared on `/tmp/base` when differing):**
- `p01_empty_base`, `p07_all_iter`, `p09_empty_base_empty_child`, `p11_empty_chain`, `/tmp/probes/p10_nonempty_checks`, corpus `g25_028`: all match CPython on both builds.
- Empty `E(0)` for all five kinds, and calls in a list/dict (`p05`), attribute (`p06`), argument (`p07`): compile-time refusal by name on both builds; CPython raises TypeError. Base wrongly succeeded, printing `<F: 0>`.
- `_X`-only member, enum referenced through a tuple/variable, `+IntEnum`, StrEnum dict-key lookup: differ from CPython **identically on base** (pre-existing).

**Tests:** `test_ail_fuzz80` and `test_ail_safetynet` pass on HEAD (`-j 2`, 0 failed). `update_manifest.py --check` rc 0.

**Claims:** fix/commit, empty-enum compile/iterate/base, call-site refusal, `g25_028` match, manifest check, no DEVLOG/DIFFERENCES: verified. Other listed test modules not re-run (out of review scope): unverified.

**Speed:** no generated-code change; `g25_028` C is byte-identical to base, as is a no-enum program.

Pre-existing only: underscore-prefixed members, dynamic class references, unary `+` on IntEnum, StrEnum plain-`str` key lookup.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1000103, "input": 68688, "output": 5508, "reasoning": 10707, "cache.write": 0, "cache.read": 915200}]

FINAL VERDICT: ACCEPT  2026-10-23T08:07:13Z
