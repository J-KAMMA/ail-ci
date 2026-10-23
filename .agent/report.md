# job job-fuzz67-10231453  started 2026-10-23T05:54:16Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Committed `209f8ae` on `job-fuzz67-10231453` (not pushed).

- Fixed class attributes being copied per instance on the general path: class attributes now live on the class object, instances fall back to them, and `C.x` / `cls.x += ...` work. Array-entry programs keep the old behavior.
- Added `AIL_CURRENT/test_ail_fuzz67.py` with 9 class/instance-variable programs, checked against CPython on both builds.
- Final-commit tests pass: `test_ail_fuzz67`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, plus `test_ail_gcstress` and `test_ail_gcroots`.
- Probes `p01`–`p14` and `p16` match CPython on both builds; `p11` matches exit 1 and `IndexError`.
- `p07`/`p15` (`__slots__`) still differ, but identically on base commit `6d8677d`, so pre-existing: AIL ignores slots where CPython raises `AttributeError` (and `vars()` raises `TypeError`).
- No `DEVLOG` or `DIFFERENCES` file exists in this worktree, so no entries were added.
[cost $0.0000, opencode tokens {"total": 8155206, "input": 461752, "output": 20896, "reasoning": 32366, "cache.write": 0, "cache.read": 7640192}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review report

**Change:** `209f8ae` — class attributes moved from per-instance copies to a class-owned table (`cruntime.py`, `pyboxed2.py`), plus `test_ail_fuzz67.py`.

**Direct behaviour:** normal instance/class reads, inheritance, `C.x`, `cls.x +=`, shared mutable class lists, nested lists, and method/classmethod counters match CPython on both builds (`p1b`, `p3`, `p6`–`p10`, `p13`, `p14`, `p16`, `e1`). Programs with no classes produce byte-identical `program.c` (`plain2`).

### Defects (new, caused by this change)

1. `getattr` / `hasattr` no longer see class attributes. `safetyrt.py:1303` (`ail2a_find`) scans only instance attrs.
```python
class C:
    x = 5
    xs = [1]
    def __init__(self): self.y = 2
c = C()
print(getattr(c, 'x', 'missing'), getattr(c, 'xs', 'missing'))
print(hasattr(c, 'x'), hasattr(c, 'y'), hasattr(c, 'z'))
print(getattr(c, 'x'))
```
Expected: `5 [1]` / `True True False` / `5`. Actual on HEAD (both builds): `missing missing` / `False True False`, then `AttributeError: 'C' object has no attribute 'x'`. Base matches CPython exactly.

2. `str.format` attribute fields lost the same fallback. `cruntime.py:17762` (`ail_meth_inst_getattr_by_name`).
```python
class C:
    xs = [1]
c = C()
print('{0.xs}'.format(c))
```
Expected: `[1]`. Actual on HEAD: `AttributeError: 'C' object has no attribute 'xs'`, exit 1. Base matches CPython.

3. Static kind inference still trusts the class-body literal after a class attribute is rebound, giving a silent wrong answer (and a segfault in a related case). `pyboxed2.py:3479`.
```python
class C:
    x = [0]
c = C()
C.x = {'a': 4, 'b': 5}
print(len(c.x))
for k in c.x:
    print(k)
```
Expected: `2`, `a`, `b`. Actual on HEAD: `2`, `a`, `4`, exit 0. (`k9`: list → str indexing segfaults.) Base rejects `C.x = ...`, so this path is newly reachable.

### Pre-existing (same on base `6d8677d`)

- `__slots__` is ignored (`p18`: `c.b = 3` succeeds instead of `AttributeError`).
- Class-body reference to an earlier class attr (`b = a + 1`) is refused (`p11`); `del c.attr` and `C.__name__` are refused/unsupported (`p1`, `p4`).

### Tests / checks

- `test_ail_fuzz67.py` and `test_ail_safetynet.py`: pass (`-j 2`).
- `test_ail_files.py` and `test_ail_corpus_findings3.py`: pass; `gcstress`/`gcroots` not re-run.
- `tools/update_manifest.py --check`: passes.
- icount unavailable (`perf_event_open` denied); wall-clock hot-loop probe showed no slowdown (HEAD 0.07s vs base 0.09s).
- Report claims: class-table fix and `C.x`/`cls.x +=` verified; “instances fall back to them” is false for `getattr`/`hasattr`/`str.format`; slot claim verified pre-existing; DEVLOG/DIFFERENCES absence verified.

VERDICT: FIX
[cost $0.0000, opencode tokens {"total": 3351764, "input": 167439, "output": 10781, "reasoning": 22568, "cache.write": 0, "cache.read": 3150976}]

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Committed `eb1db79` on `job-fuzz67-10231453` (not pushed).

Fixed all three review defects:
- `getattr`/`hasattr` now fall back to the class attribute table (`safetyrt.py`).
- `str.format` attribute fields use the same fallback (`cruntime.py`).
- Static kind inference no longer trusts class-body literals once class attributes are rebindable (`pyboxed2.py`).

Added the `attr_fallback` case to `test_ail_fuzz67.py`, covering inheritance, dynamic lookup, formatting, list→dict and list→str rebinding.

Verification on final commit:
- Probes `d1`–`d3`, `p4`–`p7`: both builds match CPython, exit 0.
- `test_ail_fuzz67`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: 4/4 pass (`-j 2`).
- `tools/update_manifest.py --check`: passes.
- No `DEVLOG` or `DIFFERENCES` file exists in this worktree, so no entries were added.
- Pre-existing `__slots__` differences remain unchanged.
[cost $0.0000, opencode tokens {"total": 1483529, "input": 160667, "output": 7241, "reasoning": 5925, "cache.write": 0, "cache.read": 1309696}]

## review 1 failed to run: Continue if you have next steps, or stop and ask for clarification if you are unsure how to proceed. [cost $0.0000, opencode tokens {"total": 8443962, "input": 471907, "output": 17514, "reasoning": 39661, "cache.write": 0, "cache.read": 7914880}] (cut off after 60 minutes) 

## review 1
[model opencode/deepseek-v4.1-flash-free]
(no final text)
[cost $0.0000, opencode tokens {}]
(cut off after 60 minutes)

FINAL VERDICT: ERROR  2026-10-23T09:07:25Z
