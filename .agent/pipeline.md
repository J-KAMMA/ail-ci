# job job-integ1-10230230  started 2026-10-22T17:31:39Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
(no final text)
[cost $0.0000, opencode tokens {"total": 5549930, "input": 102395, "output": 13454, "reasoning": 16481, "cache.write": 0, "cache.read": 5417600}]
(cut off after 100 minutes)

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Integration review**

Branches and commits look correctly cherry-picked (c169 4, cov6 4, fuzz8 3, intenum4 3 code commits; `.agent`/`corpus` changes excluded). `update_manifest.py --check` and `tools/diff_ids.py --check` pass; all branch DIFFERENCES/DEVLOG rows survive (ids renumbered C170–C187).

Targeted tests on HEAD (`par_check.py -j 2`): test_ail_c169, test_ail_fuzz8, test_ail_intenum4, test_ail_stdlib5, test_ail_stdlib6, test_ail_safetynet, test_ail_files, test_ail_corpus_findings3, test_ail_dunders — **9/9 pass**. Full suite was not run (per review rules); the DEVLOG claim that it was run is unverified (worker report is empty).

Probes (`/tmp/rprobes/`):
- `intenumops.py`, `indexbounds.py`, `itertoolsprobe.py` — match CPython on both builds.
- `hashmix.py`, `hashmix2.py`, `intenumdict.py` — **fail on HEAD on both builds** (details below); `/tmp/base` and the intenum4 branch tip match CPython.
- `lib6probe.py`, `cov6more.py` — stdout matches except the documented `AddressValueError`/`ValueError` alias; base refuses the whole module.

**Defects**

1. **IntEnum/IntFlag dict/set lookup regression for values whose CPython hash differs from the value.** Probe `/tmp/rprobes/intenumdict.py`:
```python
from enum import IntEnum
class E(IntEnum):
    NEG = -1
    BIG = 2**61
    SMALL = 3
print({-1: 'a'}.get(E.NEG), E.NEG in {-1: 'a'})
print({2**61: 'b'}.get(E.BIG), E.BIG in {2**61: 'b'})
print({3: 'c'}.get(E.SMALL), E.SMALL in {3: 'c'})
print(E.NEG in {-1}, E.BIG in {2**61})
```
Expected: `a True` / `b True` / `c True` / `True True`.
Actual HEAD (general and default): `None False` / `None False` / `c True` / `False False`. Base and `job-intenum4` tip match CPython.

Cause: the conflict in `prelude_enum.__hash__` was resolved to cov6's `return hash(self.value)` and cov6's removal of the dunderrt IntEnum re-hash line. The dict path (`ail_dun_hash`) then applies `ail_obj_hash` to the already-Python-hashed int, so `E.BIG`/`E.NEG` land in different buckets than the equal int keys (`ail_obj_hash(value)`). Keeping intenum4's enum hash path (or special-casing IntEnum in the runtime) while retaining cov6's `Fraction.__hash__` fix would preserve both fixes; the current resolution loses intenum4's dict compatibility.

2. **Coverage gap:** `AIL_CURRENT/test_ail_intenum4.py` (800 lines) is not added to `ail_check.MODULES`, so neither the full suite nor `tools/ci_shards.py` ever runs it. The intenum4 commits that touch `dunderrt.py`/`prelude_enum.py` are therefore unguarded in CI; this is how defect 1 escaped.

Pre-existing differences: none found for the probes above.

VERDICT: FIX
1. IntEnum/IntFlag dict and set lookups miss equal int keys for `-1` and `2**61` (and any value where CPython's hash differs from the value); expected `a True/b True/True True`, actual `None False/None False/False False` on both builds. Probe: `/tmp/rprobes/intenumdict.py`.
2. Register `test_ail_intenum4` in `ail_check.MODULES` so the integrated suite actually exercises the intenum4 changes.
[cost $0.0000, opencode tokens {"total": 2885293, "input": 98660, "output": 9951, "reasoning": 21738, "cache.write": 0, "cache.read": 2754944}]

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed as `f252de4`.

- IntEnum/IntFlag now hash raw values for dict/set buckets, with `hash()` applying `int.__hash__` only for marked members; cov6's Fraction fix retained.
- Registered `test_ail_intenum4` in `ail_check.MODULES`; `update_manifest.py --check` and `diff_ids.py --check` pass.
- Probes: `intenum_hash_bounds`, `intenum_hash_routes`, `intenumdict`, `hashmix`, `hashmix2`, `intenumops` all match CPython on both builds.
- Targeted `par_check.py -j 2`: 9/9 pass on the final commit. Full suite left to CI per the job rules.
[cost $0.0000, opencode tokens {"total": 3966348, "input": 217643, "output": 10280, "reasoning": 14137, "cache.write": 0, "cache.read": 3724288}]

## review 1
[model opencode/deepseek-v4.1-flash-free]
**Review: integration job (HEAD `f252de4`, base `work` = `c1b039a`)**

Targeted tests on HEAD (`par_check.py -j 2`): `test_ail_intenum4`, `test_ail_safetynet`, `test_ail_stdlib5`, `test_ail_stdlib6`, `test_ail_c169`, `test_ail_fuzz8` — 6/6 pass. `update_manifest.py --check`, `diff_ids.py --check` pass; `update_manifest.py` leaves the tree clean. Perf counting was not possible (`perf_event_open: Permission denied`), so no speed numbers.

**Probes (all in /tmp/rprobes, both builds against CPython)**

- `h5`, `h6`, `h7`, `h10` (large/negative/boundary IntEnum & IntFlag hash, dict/set both ways): match on HEAD and base. The new `__ail_int_enum__` marker restores what cov6 removed; verified.
- `h2` (Fraction↔IntEnum dict lookup): fails, but identically on base — pre-existing.
- `h4` (`hash(plain Enum)`): value differs from CPython, but identically on base — pre-existing.
- `h8` (StrEnum↔str dict interchange): fails, but identically on base — pre-existing.
- `h3` (custom class `__hash__` without `__int__`): matches.
- **`f1`, `f2`, `f3` (large integral Fraction): HEAD fails in both builds; base passes.**

**Defect**

1. Integral `Fraction` hashing is broken after the cov6 fix was combined with the still-rehashing dict path. `prelude_fraction.py` now returns `hash(self.numerator)` from `__hash__`, but `ail_dun_hash` re-hashes any int result through `ail_obj_hash` (`dunderrt.py:281`). For values where `pyhash_int(n) != n` this stores the fraction under `pyhash_int(pyhash_int(n))` while an int key uses `pyhash_int(n)`, even though `Fraction(n,1) == n` and `hash(f) == hash(n)`.

Probe `/tmp/rprobes/f3.py`:
```python
from fractions import Fraction
n = 2**61 + 1
f = Fraction(n, 1)
print(hash(f) == hash(n), f in {n}, {f: 1}.get(n, 'miss'))
```
Expected (CPython and base): `True True 1`
Actual (HEAD, general and default): `True False miss`

`/tmp/rprobes/f1.py`/`f2.py` show the same for ordinary dict/set dedup (`len({n, f})` is 2 instead of 1) and for a Fraction reached through a list item / attribute / argument.

**Report claims**

- “IntEnum/IntFlag hash raw values … hash() applies `int.__hash__` only for marked members” — verified (h5/h6/h7/h10).
- “cov6's Fraction fix retained” — only partly true: retained in source, but it now breaks large integral `Fraction`↔`int` dict/set equality (f1–f3).
- “Registered test_ail_intenum4 / manifest and diff_ids checks pass” — verified.
- “Probes … all match CPython” — false as a completeness claim; their `cov6_fraction_bound.py` checks only `hash(f)==hash(n)`, not dict/set interop.
- “Targeted par_check 9/9” — not independently reproduced (I ran the six modules above, all pass).

VERDICT: FIX
1. Large integral `Fraction` no longer interoperates with equal `int` dict/set keys (`/tmp/rprobes/f3.py`: expected `True True 1`, got `True False miss` on both builds; base is correct). The dict/set hash path (`dunderrt.py:281`) re-hashes the already-reduced result of `Fraction.__hash__` (`prelude_fraction.py:260-262`), so the Fraction bucket differs from the equal int bucket whenever `|numerator| >= 2**61 - 1`.
[cost $0.0000, opencode tokens {"total": 1582290, "input": 61294, "output": 8012, "reasoning": 13080, "cache.write": 0, "cache.read": 1499904}]

FINAL VERDICT: FIX  2026-10-22T20:42:34Z
