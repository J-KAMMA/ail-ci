# job job-rbfuzz49-10240914  started 2026-10-24T00:15:04Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Re-applied `job-fuzz49` onto this tree, preserving the current `divmod` dispatch while adding the in-place operator dispatch.

**Changes**
- `dunderrt.py`: added `__iadd__/__isub__/__imul__/__iand__/__ior__/__ixor__` dispatch, appended only for programs that define one; kept `__divmod__`/`__rdivmod__`.
- `safetyrt.py`: `NotImplemented` from an in-place method falls back to the plain/reflected operator.
- `pyboxed2.py`: in-place class kind is invalidated; augmented-assignment targets never keep a trusted class kind.
- Added `test_ail_fuzz49.py`, registered in `ail_check.MODULES` and `tools/ci_shards.json`.
- Added `DEVLOG` (2026-10-24) and `DIFFERENCES` (`C?-job-rbfuzz49-10240914-1`) entries; refreshed `MANIFEST.json`.

**Verification**
- `python3 tools/update_manifest.py --check`: 0.
- Required tests on final commit: `test_ail_fuzz49`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 38 tests, OK (1 skipped).
- 8 probes in `/tmp/probes/` covering all six ops, name/attribute/list/dict/argument targets, aliasing, changed return type, `NotImplemented`, inheritance/fallback, primitives (empty/negative/width) and stale class kinds: all matched CPython on both `g` and `d` builds.

Note: `tools/diff_ids.py` does not exist in this tree, so it could not be run.

Commit: `c379d7c`
[cost $0.0000, opencode tokens {"total": 933586, "input": 35588, "output": 9678, "reasoning": 0, "cache.write": 0, "cache.read": 888320}]
    tool time: bash 11.5 min
        436s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest -q test_ail_fuzz49 test_ail_safetynet te
        210s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest -q test_ail_fuzz49 test_ail_safetynet te
         42s bash   for p in /tmp/probes/*.py; do echo "=== $(basename $p) ==="; bash ~/tools/cmp.sh "$p" "$PWD" 2>&1 | grep -v '^
          2s bash   git fetch https://github.com/J-KAMMA/ail-ci.git job-fuzz49-10231204 2>&1 | tail -5
          0s bash   git status && git log --oneline -5 && ls
          0s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT/python/pkg-v12 && python3 -c " import dunderrt, safetyrt print(
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'EOF' from pathlib import Path p=Path('AIL_CURRENT/ail_check

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: re-apply job-fuzz49 (`c379d7c`)

**Diff vs the accepted job.** `git diff 4b18b68 FETCH_HEAD` matches the worker's change byte-for-byte except expected context: this tree already has `__divmod__/__rdivmod__`, and `ENUMS_INPLACE` anchors on `AIL_D2_DIVMOD, AIL_D2_RDIVMOD` instead. `test_ail_fuzz49.py` is identical to the accepted job. `update_manifest.py --check` = 0.

**Probes** (18 in `/tmp/rprobes`, both `g` and `d`):
- p2 alias/mutate, p3 arg/attr/list/dict, p4 `__iadd__`→None, p5 unaffected primitives, p6 parameter shadowing aug target, p8 loops, p9 global/closure retype, p10 inheritance/subclass, p11 raising `__iadd__`, p12 item/attr alias with new object, p13 bytes, p14 `self += ...`, p15/16 aug-target kind invalidation + methods, p17 deque `*=`, p18 bytes/bytearray alias: **all match CPython on both builds**.
- p1 (`__iadd__`→NotImplemented, right `__radd__`): feature fallback works; one line differs due to `a + b` with both operands of the same class defining only `__radd__` (AIL calls it, CPython raises TypeError). **Identical on `/tmp/base`** — see Pre-existing.
- C for programs without in-place methods (p5, p7/Counter): identical to base in both builds. Programs that aug-assign an instance differ only through the intended kind invalidation; p15/16 still match CPython.

**Tests:** `par_check -j 2 test_ail_fuzz49 test_ail_safetynet test_ail_files test_ail_corpus_findings3` → 4 modules, **0 failed**.

**Report claims:** all verified, except (a) the exact "8 probes" cannot be re-observed but independent probes confirm the same behaviours; (b) `tools/diff_ids.py` indeed does not exist — noted correctly.

**Speed:** not measured: `tools/icount.c` gets `perf_event_open: Permission denied`. C comparison shows the only gdev-affected program shape (typed deque, which defines `__imul__`) gains one predictable branch in the in-place helpers plus one `d2` setup; no gdev program performs an augmented deque op, so no hot path changed.

**Pre-existing (does not block):** `a + b` where both operands have the same user class and only `__radd__` is defined returns a value instead of CPython's TypeError; base behaves identically (p1).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 4043372, "input": 120975, "output": 25403, "reasoning": 6946, "cache.write": 0, "cache.read": 3890048}]
    tool time: bash 7.0 min
        263s bash   date && cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_fuzz49 test_ail_safetyn
         30s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/*.py; do echo "=== $(basename $p) ==="; bash ~/too
         22s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/p8_loop.py /tmp/rprobes/p9_global.py /tmp/rprobes/
         21s bash   cd /tmp && rm -rf /tmp/dbgroot && mkdir -p /tmp/dbgroot && for wt in /home/runner/work/ail-ci/ail-ci /tmp/base
         20s bash   cat > /tmp/rprobes/p18_bytes_alias.py <<'EOF' x = b"a" y = x x += b"b" print(x, y) ba = bytearray(b"a") bb = b
         11s bash   cat > /tmp/rprobes/p15_add_only.py <<'EOF' class A:     def __init__(self, n):         self.n = n     def __ad
         10s bash   cat > /tmp/rprobes/p13_bytes.py <<'EOF' ba = bytearray(b"ab") ba += b"cd" print(bytes(ba)) b = b"xy" b += b"z"
         10s bash   cd /home/runner/work/ail-ci/ail-ci && bash ~/tools/cmp.sh /tmp/rprobes/p15_add_only.py "$PWD" 2>&1 | grep -v '

FINAL VERDICT: ACCEPT  2026-10-24T00:43:24Z
