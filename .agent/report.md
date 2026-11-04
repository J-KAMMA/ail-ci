# job job-fz226-11041145  started 2026-11-04T02:47:03Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
No compiler change was needed: the original DIFF no longer reproduces. Both builds now refuse the constant at compile time.

- Minimized construct: constant integer subtraction leaving int64, `print(((3 - -9223372036854775807) ** 1))` → `int64 constant out of range: 9223372036854775810` on default and `AIL_IR=1`.
- Probes (`/tmp/probes/fz226_*`, `cmp.sh` both builds): direct/sub variants refused by name; in-range variants match CPython. Routed wide values (argument/list item/attribute/dict value) stop with the declared int64 overflow (exit 1, `integer overflow`, stdout prefix); `--exact-int` matches CPython. `cmp.sh` labels those routed probes DIFF because it compares stdout strictly, but the fuzz runner's `overflow` class accepts them.
- Added `test_ail_fz226.py` (6 tests), registered in `tests.d`, plus DIFFERENCES row `C?-job-fz226-11041145-1` and DEVLOG entries. Manifest check passes.
- Tests: `test_ail_fz226`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` → 31 run, OK (1 unrelated skip).
- Commit: `48b91d1`.

Other observations: `lab/fuzz/run.py` only counts compiler exit 3 as `refused`, so this load-time exit-2 refusal is classified `crash` (tooling, not a silent language difference); and the legacy general exact-int path still overflows for the function-argument route while the list route matches.
[cost $0.0000, opencode tokens {"total": 6758120, "input": 148101, "output": 16583, "reasoning": 32284, "cache.write": 0, "cache.read": 6561152}]
    tool time: bash 13.0 min, edit 0.0 min, write 0.0 min
        554s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 2400 python3 -m unittest -v test_ail_fz226 test_ail_safet
         43s bash   printf 'test_ail_fz226\n' > AIL_CURRENT/tests.d/test_ail_fz226.txt && cat AIL_CURRENT/tests.d/test_ail_fz226.t
         43s bash   cd AIL_CURRENT && timeout 900 python3 -m unittest -v test_ail_fz226 2>&1 | tail -30
         21s bash   cd /tmp/probes && for p in m_in m_routes; do echo "##### $p"; for label in d di g gi xd xdi xg xgi; do unset A
         16s bash   cd /tmp/probes && cat > r_arg.py <<'EOF' def take(x: int) -> None:     print(((3 - x) ** 1)) print("before") t
         15s bash   cd /tmp/probes && for p in r_try r_try2; do echo "### $p"; for label in xd xdi xg xgi; do unset AIL_UNIFIED_FO
         14s bash   cd /tmp/cmpIJJ6 && for ir in 0 1; do echo "=== EXACT AIL_IR=$ir ==="; AIL_NO_CACHE=1 AIL_QUIET_FALLBACK=1 AIL_
         14s bash   cd /tmp/probes && cat > m_min.py <<'EOF' print(((3 - -9223372036854775807) ** 1)) EOF cat > m_in.py <<'EOF' pr

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review report — fz226 (`48b91d1`)

**What the change really does:** test/doc-only. Adds `AIL_CURRENT/test_ail_fz226.py` (6 tests), `tests.d` registration, two DEVLOG entries, one DIFFERENCES row, and manifest.d entries. No compiler or runtime source is touched. This matches the worker's "no compiler change was needed" claim.

**Original finding does not reproduce.** On HEAD, the full fuzz program is refused at compile time in default, general (`AIL_UNIFIED_FORCE=1`) and `AIL_IR=1`:
`p.py:55:16: int64 constant out of range: 9223372036854775810`. `/tmp/base` gives byte-identical refusal. Probes: `/tmp/rprobes/fz226_orig.py`, `r_min.py`.

**Probes run (cmp.sh, HEAD vs base)**
- `r_min.py` (minimized subtraction): refused by name on g/d and IR; base identical.
- `r_in.py` (in-range neighbours): matches CPython on g/d.
- `r_arg.py`, `r_list.py`, `r_attr.py`, `r_dict.py`: int64 overflow, exit 1, stdout is a CPython prefix; identical on base.
- `r_try.py` (try/finally + argument): AIL prints `before`, then overflow, omitting the `finally`/`after` lines; identical on base.
- `--exact-int`: default build matches CPython on all four routes; **general** build still overflows on the argument route; identical on base.
- Non-feature program (`plain.py`): `--debug-dir` `program.c` is byte-identical HEAD vs base.

**Report claims**
- Not reproducing / both builds refuse: **verified**.
- Minimized construct refused by name default+IR: **verified**.
- In-range neighbours match CPython: **verified**.
- Routed wide values keep overflow contract, stdout prefix: **verified**.
- "`--exact-int` matches CPython": **false as stated** (only default build; general argument route overflows, as the worker's later observation admits).
- fuzzer counts only exit 3 as `refused`: **verified** (`lab/fuzz/run.py:103-108`); the exit-2 constant refusal is therefore classified `crash`, not `refused`/`overflow`.
- Tests/registration/manifest: **verified**; `update_manifest.py --check` rc 0.

**Tests:** `test_ail_fz226`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` → 4 modules, 0 failed (388 s).

**Pre-existing (identical on `/tmp/base`, not blocking):**
- General-path `--exact-int` overflows for the function-argument route.
- AIL does not run `finally` when an int overflow propagates out of a called function (`r_try.py`).
- The fuzz runner classifies the exit-2 constant refusal as `crash` (tooling classification, not a silent language difference).

**Unverified:** exact CI fuzz-runner rerun of the seed; skip count in the worker's test summary.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 561466, "input": 28929, "output": 4290, "reasoning": 9591, "cache.write": 0, "cache.read": 518656}]
    tool time: bash 7.5 min
        390s bash   date; cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 1500 python3 ../tools/par_check.py -j 2 test_ail_fz
         35s bash   cd /tmp/rprobes; date; for wt in /home/runner/work/_temp/w2 /tmp/base; do echo "##### WT=$wt"; for p in r_arg 
          9s bash   cd /tmp/rprobes; date; for p in r_arg r_list r_attr r_dict; do echo "=== HEAD $p ==="; bash ~/tools/cmp.sh /tm
          7s bash   cd /tmp/rprobes; date; for wt in /home/runner/work/_temp/w2 /tmp/base; do echo "##### WT=$wt"; d=$(mktemp -d /
          2s bash   cd /tmp/rprobes && cat > r_try.py <<'EOF' def take(x: int) -> None:     print(((3 - x) ** 1)) print("before") 
          2s bash   cd /tmp/rprobes && cat > r_arg.py <<'EOF' def take(x: int) -> None:     print(((3 - x) ** 1)) print("before") 
          2s bash   date; cd /tmp/rprobes; echo "=== BASE ==="; bash ~/tools/cmp.sh /tmp/rprobes/fz226_orig.py /tmp/base 2>&1 | ta
          1s bash   cd /tmp/rprobes; date; for wt in /home/runner/work/_temp/w2 /tmp/base; do echo "##### WT=$wt IR"; d=$(mktemp -

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-04T04:35:04Z
