# job job-prog4-11020712  started 2026-11-01T22:13:11Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the review's defect: `_provably_nonzero` no longer rebinds the `UnaryOp` before reading `node.op`, so signed literal divisors keep the hybrid analysis alive.

Probes (all under `--cpython`, stdout/exit match CPython):
- `p_fdivneg.py` — review probe: `accelerated: ["add1","fdivneg","head","modp"]`
- `p_signedlit.py` — `/-2.0`, `//-2.0`, `%-2.0`, `/+2.0`, `//-2`, `%+3` accelerated; `/-0.0` refused
- `p_mixed_bad.py` — all six functions accelerated

Added the signed-literal regression case to `test_ail_prog4.py`, added the DEVLOG entry, and ran `update_manifest.py` + `--check`.

Tests (`-j 2`): `test_ail_prog4`, `test_ail_cpython_hybrid`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — all pass, 0 failed.

Committed as `f92e963`; general-path C emission was not touched.
[cost $0.0000, opencode tokens {"total": 545179, "input": 19792, "output": 4843, "reasoning": 2144, "cache.write": 0, "cache.read": 518400}]
    tool time: bash 4.9 min, edit 0.0 min
        266s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c
         18s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 900 python3 tools/par_check.py -j 2 test_ail_prog4 2>&1 | tail -
         11s bash   mkdir -p /tmp/probes && cd /tmp/probes && cat > p_fdivneg.py <<'PY' def add1(x: int) -> int: return x + 1 def 
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c
          0s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 900 python3 tools/par_check.py -j 2 test_ail_prog4 2>&1 | tail -
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git log --oneline -10 && git status --short
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git show --stat HEAD | head -60
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git add AIL_CURRENT/ail_cpython_hybrid.py AIL_CURRENT/test_ail_prog4.py 

## review 0
[model opencode/deepseek-v4.1-flash-free]
## review 2

**What the change does:** It keeps the `UnaryOp` in a separate variable in `_provably_nonzero` so reading `node.op` after taking `node.operand` no longer raises `AttributeError`; it also adds a signed-literal regression case to `test_ail_prog4.py`, a DEVLOG entry and the manifest hash. General-path C emission is untouched. This matches the worker report.

**Review defect 1:** fixed. `p_fdivneg.py` on HEAD gives `accelerated: ["add1","fdivneg","head","modp"]`, stdout/exit match CPython; on `/tmp/base` it still gives `accelerated: []` and `no extension: 'Constant' object has no attribute 'op'`.

**Probes (hybrid `build --cpython`, HEAD):**
- `p_fdivneg.py` (review probe): accelerated, match.
- `p_signs.py` (`/-2.0`, `//-2.0`, `%-2.0`, `/+2.0`, int `//-2`, `%+3`, `-True`, `+True`, `-0.0`, `-0`): matching; the six non-zero signed literals accelerated, `/-0.0`, `//-0`, `%-True`, `/+True` refused, stdout/exit match.
- `p_types.py` (int/float numerator and signed int/float divisor): accelerated ones match.
- `p_route.py` (argument, list item, dict value, attribute): match.
- `p_strdiv.py` (str with signed literal divisor): only `sadd` accelerated; `sdiv` refused by the emitter, stdout match.
- `p_zerolits.py`, `p_complex.py`, `p_c1.py`, `p_c2.py`, `p_more2.py`: match CPython.
- No-feature C identity: `p_nofeature.py` general build `program.c` byte-identical HEAD vs `/tmp/base`.

**Report claims:**
- `_provably_nonzero` no longer rebinds: **verified**.
- review probe accelerated list: **verified** (same set).
- `/-2.0`, `//-2.0`, `%-2.0`, `/+2.0`, `//-2`, `%+3` accelerated, `/-0.0` refused: **verified**.
- mixed module all functions accelerated: **verified** (equivalent mixed probes).
- tests `test_ail_prog4`, `test_ail_cpython_hybrid`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: **verified**, all pass, 0 failed.
- manifest: **verified** (`update_manifest.py --check` rc 0).
- general C untouched: **verified**.

**Pre-existing (identical on `/tmp/base`, no block):** a complex literal divisor (`x / -2j`) disables acceleration for the whole module (`p_c1.py`); double unary `--2.0` leaves only the unrelated function accelerated (`p_c2.py`); the review-1 aug-assign float hole (`x /= y`) is untouched and not re-probed.

**Unverified:** instruction counts (change is build-time analysis only, no runtime/hot-code change); worker's exact probe filenames.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 573611, "input": 14291, "output": 5433, "reasoning": 6175, "cache.write": 0, "cache.read": 547712}]
    tool time: bash 6.0 min
        171s bash   cd /home/runner/work/ail-ci/ail-ci && date && timeout 900 python3 tools/par_check.py -j 2 test_ail_files test_
        153s bash   date; cd /home/runner/work/ail-ci/ail-ci && timeout 900 python3 tools/par_check.py -j 2 test_ail_prog4 test_ai
          8s bash   cat > /tmp/rprobes/hcmp.sh <<'SH' #!/bin/bash # hcmp.sh SRC WORKTREE src=$1; wt=$2; d=$(mktemp -d /tmp/hcmpXXX
          8s bash   cd /tmp/rprobes && for p in p_fdivneg p_signs; do echo "===== $p BASE"; ./hcmp.sh $p.py /tmp/base; done
          5s bash   cat > /tmp/rprobes/p_zerolits.py <<'PY' def fz0(x: float) -> float: return x / -0.0 def fz1(x: float) -> float
          4s bash   cat > /tmp/rprobes/p_types.py <<'PY' def ifd(x: int) -> float: return x / -2.0 def iffd(x: int) -> float: retu
          4s bash   cat > /tmp/rprobes/p_strdiv.py <<'PY' def sdiv(x: str) -> str:     return x / -2.0 def sadd(x: str) -> str:   
          2s bash   cat > /tmp/rprobes/p_more2.py <<'PY' def d1(x: float) -> float: return x / - 2.0 def d2(x: float) -> float: re

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-01T23:43:31Z
