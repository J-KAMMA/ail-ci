# job job-fuzz90-10231630  started 2026-10-23T07:31:00Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Commit `60a764e` on `job-fuzz90-10231630`.

**Fixed**
- `is` / `is not` on equal str/bytes was a silent `False` where CPython interns constants and returns `True`.
- Direct constant pairs are refused at compile time; values reaching `is` through arguments, list items, attributes, dict values, or bytes/bytearray instances stop by name with `C?-job-fuzz90-10231630-1`.
- Added `AIL_CURRENT/test_ail_fuzz90.py` (5 tests), registered it in `ail_check.py`, refreshed `MANIFEST.json`, and created `DEVLOG.md` / `DIFFERENCES.md` records.

**Probes**
- Same stdout, both builds: `p01`–`p08`, `chain_safe_huge`, `str_allowed`.
- Named runtime stop, both builds: `p09`, `p09d_typed`, `str_id_cases`, `str_rt_shapes`, `str_rt_attr`, `str_rt_dict`, `bytes_id_cases`.
- Named compile refusal, both builds: `p09b`, `p09c`.
- Other difference: `p10_chain_huge_neg.py` fails with `integer overflow` on both base `f01efa7` and HEAD, before any output; pre-existing, not fixed.

**Tests on final commit**
- `test_ail_fuzz90`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_silent2`, `test_ail_deqctr`: 6 modules, 0 failed, 507s.
- `python3 tools/update_manifest.py --check` passed. No push.
[cost $0.0000, opencode tokens {"total": 7452426, "input": 482948, "output": 17479, "reasoning": 31679, "cache.write": 0, "cache.read": 6920320}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Review**

Diff is confined to `cruntime.py` (`ail_is`), `numidentity.py` (constant-pair refusal), test registration, and records. Generated C for a program that never uses `is` is byte-identical to base (only `native_report.json` differs).

**Defects**

1. `cruntime.py:14406` aborts for *any* two distinct instances whose class name is `bytes`/`bytearray`, without comparing contents. Unequal and mutable values are never interned in CPython, so this turns correct programs into exit 1.
   - `b_uneq_arg.py`:
     ```python
     def same(a, b):
         return a is b
     def main() -> None:
         print(same(b"a", b"b"))
     main()
     ```
     CPython/base: `False`, exit 0. HEAD: no stdout, exit 1, `` `is` between bytes ... ``.
   - `ba_eq.py`: `same(bytearray(b"a"), bytearray(b"a"))` → CPython/base `False`; HEAD exit 1. Same for `bytes([97]) is bytes([98])` (base/CPython `False`).
   - The check should require equal contents at minimum, and `bytearray` should never be refused (CPython does not intern mutable bytearrays).

2. Secondary: equal dynamically-built strings are now refused at run time. `a = "x" * n; b = "x" * n` prints `False` on CPython and base, but HEAD exits 1 with `` `is` between equal strings or bytes ``. The task asked for refusal by name at compile time; this is a run-time abort of a program that previously matched.

**Claims**

- Silent wrong answer for equal `str`/`bytes`: verified — base prints `False` where CPython prints `True`.
- Compile-time refusal of two text constants: verified by the new test module.
- Values through arguments/list items/attributes/dict values stop by name: verified by the new test, but the bytes branch is over-broad (defect 1); the test only uses equal bytes, so it missed it.
- `test_ail_fuzz90` + `test_ail_safetynet`: verified, `2 modules, 0 failed, 124s`. `test_ail_files` / `test_ail_corpus_findings3` not re-run (outside reviewer scope).
- `update_manifest.py --check`: verified, exit 0.
- `p10` huge negative chain overflow: verified pre-existing; both base and HEAD print `integer overflow` for `-2**63 < f(0) < 0` before any output.
- Speed: not measured; `ail_is` handles only the `is` operator, not a hot numeric/container path.

**Pre-existing**

- `-2**63` in a chain overflows on both base and HEAD (CPython prints `False`). Not blocking.

VERDICT: FIX
1. `cruntime.py` bytes/bytearray branch must compare contents and must not refuse `bytearray`; probes `b_uneq_arg.py`, `ba_eq.py`, `byt_ctor_uneq.py` show base/CPython `False`, HEAD exit 1.
2. The named run-time stop on equal runtime-built strings (`s_dyn_eq.py`: CPython/base `False`, HEAD exit 1) should be removed or made a compile-time refusal.
[cost $0.0000, opencode tokens {"total": 1028062, "input": 107616, "output": 4334, "reasoning": 12048, "cache.write": 0, "cache.read": 904064}]

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed as `2348d81`.

Changes:
- `ail_is` now refuses only equal text CPython may share (literal pairs, empty/one-character values), compares bytes contents, and never refuses `bytearray`.
- Equal longer strings/bytes built at run time match CPython again.
- Updated records, manifest, and `test_ail_fuzz90.py`.

Probes (`bash ~/tools/cmp.sh ...`, both builds):
- Match CPython: `b_uneq_arg`, `byt_ctor_uneq`, `ba_eq` (unequal/bytearray lines), `bytes_dyn_multi_not`, `str_dyn_only`, `s_dyn_eq`, `b_dyn_eq`, `bytes_multi_dyn`.
- Refused by name: `str_lit_arg`, `bytes_lit_arg`, `empty_dyn`, `empty_bytes_dyn`, equal `bytes([97])`.
- Compile-time text-constant refusal still covered by the module.

Tests on final commit: `test_ail_fuzz90`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 32 tests, 0 failed, 1 skipped, 534s. `update_manifest.py --check` exit 0. Not pushed.
[cost $0.0000, opencode tokens {"total": 4257178, "input": 195703, "output": 13283, "reasoning": 15168, "cache.write": 0, "cache.read": 4033024}]

## review 1 failed to run: (no final text) [cost $0.0000, opencode tokens {"total": 268977, "input": 50484, "output": 1402, "reasoning": 1411, "cache.write": 0, "cache.read": 215680}] (cut off after 60 minutes) 

## review 1
[model opencode/deepseek-v4.1-flash-free]
(no final text)
[cost $0.0000, opencode tokens {}]
(cut off after 60 minutes)

FINAL VERDICT: ERROR  2026-10-23T10:34:22Z
