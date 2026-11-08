# job job-fz240-11081749  started 2026-11-08T08:54:16Z  worker=chain reviewer=chain (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
## Report

**Finding did not reproduce; no compiler change made.** Seed `2076507535` is now `same` in both `default` and `ir` modes (`lab/fuzz/run.py --start 2076507535 --count 1 --jobs 1`: 1/1 same per mode). `bash ~/tools/cmp.sh /tmp/probes/fz240.py $PWD` reports `g same stdout` and `d same stdout`; likewise with `AIL_IR=0`.

**Construct:** direct `float(<exact integer constant expression that leaves int64>)`, e.g. `float((4611686018427387904 * 53))`. It is folded before the int64 checks and converted to the nearest double, so it matches CPython. Assigning the same expression to an `int` local is refused by name; a wide run-time multiplication keeps the declared int64 `OverflowError`.

**Added** `AIL_CURRENT/test_ail_fz240.py` (registered via `AIL_CURRENT/tests.d/test_ail_fz240.txt`): fuzzer slice, sign/power/bool/float constant neighbours, argument/list-item/attribute/dict routes inside int64, named refusals (`v: int = 2**62 * 53`, `float(1 << 2000)`), and the declared wide-runtime overflow, on default and `AIL_IR=1`.

**Tests (final code state, `-j 2`):** `test_ail_fz240`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4/4 modules, 0 failed (339 s); `test_ail_fz240` 5/5. Manifest `--check` clean.

**Probes** (`/tmp/probes/fz240*.py`, default/IR): `fz240`, `_min`, `_flow`, `_more`, `_exact`, `_huge` match CPython or are refused by name; `_runtime` and `_local` show only the declared int64 overflow / named refusal.

**Other differences seen:** the declared int64 overflow for runtime `float(x * 53)` when `x = 2**62`; `float(1 << 2000)` refused by name (CPython raises `OverflowError`); and with `AIL_EXACT_INT=1` the default build still overflows on `v: int = 4611686018427387904 * 53` while the forced-general build prints CPython's exact value (recorded in DEVLOG, not changed).

Commits: `687f1c5` (test + records), `f71f511` (DEVLOG caveat).
[cost $0.0000, opencode tokens {"total": 2575936, "input": 90141, "output": 11038, "reasoning": 12933, "cache.write": 0, "cache.read": 2461824}]
    tool time: bash 7.2 min, edit 0.0 min, write 0.0 min
        341s bash   python3 tools/par_check.py -j 2 test_ail_fz240 test_ail_safetynet test_ail_files test_ail_corpus_findings3 2>&
         26s bash   mkdir -p /tmp/probes && cat > /tmp/probes/fz240.py <<'PY' def h0(xs: list[int]) -> int:     t: int = 0     for
         12s bash   WT=/home/runner/work/ail-ci/ail-ci; d=$(mktemp -d /tmp/manXXXX); cp /tmp/probes/fz240.py $d/p.ail; cd $d AIL_N
         12s bash   WT=/home/runner/work/ail-ci/ail-ci for p in fz240_min.py fz240_flow.py fz240_runtime.py; do echo "=== $p defau
          7s bash   cat > /tmp/probes/fz240_exact_simple.py <<'PY' v: int = 2 ** 100 print(v) print(float(v)) PY WT=/home/runner/w
          6s bash   cat > /tmp/probes/fz240_exact_local.py <<'PY' v: int = 4611686018427387904 * 53 print(v) PY WT=/home/runner/wo
          5s bash   python3 tools/par_check.py -j 2 test_ail_fz240 2>&1 | tail -30
          5s bash   cat > /tmp/probes/fz240_more.py <<'PY' print(float((1 << 100) + 1)) print(float(-(1 << 100) + 1)) print(float(

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review

**What the change does:** no compiler/runtime change. It adds `AIL_CURRENT/test_ail_fz240.py` (registered in `tests.d`, manifest updated), a `DEVLOG` entry, and one `DIFFERENCES` row. This matches the worker's statement exactly.

**Finding not reproduced (verified):** `bash ~/tools/cmp.sh /tmp/rprobes/fz240.py $PWD` on HEAD: `g same stdout`, `d same stdout`, both exit 1; identical on base `/tmp/base`; same with `AIL_IR=1`. `lab/fuzz/run.py --start 2076507535 --count 1 --jobs 1` classes seed `same` in default and ir (1/1 each). So the seed no longer differs on this tree, and no fix was owed.

**Probes (HEAD, default + IR; base where noted):**
- `fz240` (full reproducer) — same stdout as CPython on HEAD, base, and IR.
- `p_consts2` — `float(2**63)`, `2**62*53`, `1<<100`, negative, bool, `-0.0` — same stdout both builds.
- `p_routes2` — `float()` via argument, list item, attribute, dict value — same stdout both builds.
- `p_2_1023` — same; `p_huge` (`float(1<<2000)`) and `p_2_1024` — named `int64 constant out of range` refusal, identical on base.
- `p_nofeature` — unchanged (no source diff exists).
- Pre-existing/declared: `float(xs[1] + 1)` with int64 max raises the documented int64 `OverflowError`; identical on base.

**Tests:** `test_ail_fz240` 5/5 OK; `test_ail_safetynet` ok; 2/2 modules, 0 failed. `tools/update_manifest.py --check` clean.

**Report claims:** all observed claims verified (no repro, folding route, named refusals, runtime overflow contract, registration/manifest). Claim about `AIL_EXACT_INT=1` caveat not re-probed — unverified, but it is explicitly outside this finding and recorded, not presented as fixed.

**Pre-existing differences:** none new; the int64 runtime overflow and the over-range constant refusals are identical on `work`.

**Unverified:** `test_ail_files`, `test_ail_corpus_findings3` (not added/edited by this change); the `AIL_EXACT_INT=1` probe.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 350157, "input": 32226, "output": 3972, "reasoning": 5351, "cache.write": 0, "cache.read": 308608}]
    tool time: bash 3.2 min
        128s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_fz240 te
         16s bash   export AIL_IR=1; for p in fz240 p_consts2 p_routes2; do echo "===== $p IR"; bash ~/tools/cmp.sh /tmp/rprobes/$
         14s bash   cd /tmp && time bash ~/tools/cmp.sh /tmp/rprobes/fz240.py /tmp/base 2>&1 | tail -20
         13s bash   cd /tmp && time bash ~/tools/cmp.sh /tmp/rprobes/fz240.py /home/runner/work/ail-ci/ail-ci 2>&1 | tail -20
          6s bash   mkdir -p /tmp/rprobes; cat > /tmp/rprobes/p_consts.py <<'PY' print(float(4611686018427387904 * 53)) print(floa
          4s bash   grep -v '2 \*\* 1024' /tmp/rprobes/p_consts.py > /tmp/rprobes/p_consts2.py; grep -v 'xs\[1\] + 1' /tmp/rprobes
          4s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 300 python3 -B test_ail_fz240.py -v 2>&1 | t
          3s bash   for p in p_routes p_2_1024; do echo "===== $p BASE"; bash ~/tools/cmp.sh /tmp/rprobes/$p.py /tmp/base 2>&1 | g

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-08T10:30:17Z
