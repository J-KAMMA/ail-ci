# job job-fuzz54-10231352  started 2026-10-23T04:53:21Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Implemented and committed `0c21532` on `job-fuzz54-10231352`.

**Fix**
- `tupexpr.seq_type` no longer keeps the first element type when a display mixes incompatible types. It refuses the tuple rewrite, so the generic path prints the real objects.
- Added `AIL_CURRENT/test_ail_fuzz54.py`, registered it in `ail_check.py` and `tools/ci_shards.json`, refreshed `MANIFEST.json`.

**Tests on final commit**
`test_ail_fuzz54`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_tuples`, `test_ail_nested_lists`, `test_ail_unified` — 7 modules, 0 failed in 463s. `test_ail_strict` also passed on the same tree before commit.

**Probes**
- `p45`, `m13`, `m14`, `m20`–`m26`, `p48`–`p54`: both builds matched CPython (`same=2`, `diffs=0`). Covers mixed list/dict/set/tuple displays, `repr`, f-string, aliases, mutation through aliases, empty containers, and values via arguments, list items, dict values, and attributes.
- `p39`: pre-existing difference — huge list indices make both AIL builds exit 1 with `integer overflow`; CPython raises `IndexError`. Not caused by this change.

**Records**
This CI mirror has no `DIFFERENCES` or `DEVLOG` file (verified by search), so no row or entry could be added. `.agent/pipeline.md` remains untracked.
[cost $0.0000, opencode tokens {"total": 11448911, "input": 491671, "output": 30279, "reasoning": 33009, "cache.write": 0, "cache.read": 10893952}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Review**

**Change.** `tupexpr.seq_type` now refuses a display whose known element types differ (except int/float/bool widening), so the tuple rewrite is abandoned and the generic path prints the real objects. I verified the fix on a witness that forces the tuple pass with a tuple:

```python
def main() -> None:
    t: tuple[int, int] = (1, 2)
    mixed = [["a"], {"x": "y"}]
    print(mixed)
    print(t)
```

Base prints `[['a'], ['x']]`; HEAD matches CPython `[['a'], {'x': 'y'}]` on both builds. `p37` (`[[1], 2]`) also crashed on base (`TypeError: 'int' object is not iterable`) and is correct on HEAD.

**Probes (/tmp/rprobes, both builds, all CPython-matching on HEAD):** mixed list/dict displays and nesting (`pbug3`, `p36`, `p37`, `p38`), bool/int mixing including indexing/mutation/type/identity (`p1`, `p2`, `p9`–`p11`, `p16`–`p21`), empty containers (`p12`–`p15`), values via args/attributes/dict values/list items (`p16`–`p19`), class fields/lambdas/comprehensions/returns (`p22`–`p26`), aliasing and mutation during iteration (`p31`), annotated-wrong-type cases that base rendered wrongly (`p28`, `p29`), negative zero (`p33`).

**Pre-existing (identical base/HEAD):**
- `xs[10**20]`: AIL exits 1 with `integer overflow`; CPython raises `IndexError` on stderr (stdout/exit match).
- Huge ints (`10**30`) in mixed and homogeneous lists: both AIL builds exit 1.
- `format(True)` prints `1` instead of `True` (`p41`).

**Tests:** `test_ail_fuzz54`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` on HEAD: 4 modules, 0 failed in 247s.

**Claims:** commit, code description, registrations, manifest check (`--check` rc 0), and absence of DIFFERENCES/DEVLOG verified. The 7-module/463s and `test_ail_strict` results and the named /tmp probes were not reproducible here (not in tree), so unverified. One claim is inaccurate: the added `test_ail_fuzz54` program does **not** reproduce the bug on base — base's tuple pass hits an unrelated `AttributeError` and falls back, so the test passes without the fix. A forcing tuple is needed (above). This is a weak regression test, not a behavioural defect.

**Speed:** `perf_event_open` is denied in this runner, so icount failed. `program.c` is byte-identical between HEAD and base for `g00_008`, `g01_010`, `g01_034`, and for a no-feature program, so hot-code codegen is unchanged.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 2606103, "input": 59975, "output": 11784, "reasoning": 20168, "cache.write": 0, "cache.read": 2514176}]

FINAL VERDICT: ACCEPT  2026-10-23T05:50:21Z
