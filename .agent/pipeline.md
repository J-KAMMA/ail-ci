# job job-pre28-10240900  started 2026-10-24T00:00:37Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the first remaining pre13 difference, p6.

- Cause: general-path `any()`/`all()` used int-returning `ail_truthy_u`, which swallowed a raising user `__bool__`; the fused generator path also scanned past the deciding element.
- Fix: error-propagating `ail_truthy_chk` for `any`/`all`, with checked `__bool__`/`__len__` dispatch; fused path now short-circuits.
- Commit: `6db9cf3`
- Tests on final commit: `test_ail_pre28`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` → 4 modules, 0 failed (253 s).
- Probes, both builds: `p6` match, `p6c` match, `p6d` match (alias/types/empty/negative); `p7` still differs (eager inner generator), `r89` still differs (missing `finally` on early exit), `r15` already matches.
- `update_manifest.py --check` → exit 0.
[cost $0.0000, opencode tokens {"total": 3490823, "input": 119396, "output": 13300, "reasoning": 14767, "cache.write": 0, "cache.read": 3343360}]
    tool time: bash 11.7 min, write 0.0 min
        330s bash   python3 tools/par_check.py -j 2 test_ail_pre28 test_ail_safetynet test_ail_files test_ail_corpus_findings3 2>&
        255s bash   python3 tools/par_check.py -j 2 test_ail_pre28 test_ail_safetynet test_ail_files test_ail_corpus_findings3 2>&
         27s bash   for p in p6 p6c p7 r89 r15; do echo "===== $p ====="; bash ~/tools/cmp.sh /tmp/probes/$p.py $PWD; done
         22s bash   mkdir -p /tmp/probes && cat > /tmp/probes/p6.py <<'EOF' class B:     def __init__(self, v, boom):         self
         16s bash   cat > /tmp/probes/p6b.py <<'EOF' class B:     def __init__(self, v, boom):         self.v = v         self.boo
         16s bash   for p in p7 r89 r15; do echo "===== $p ====="; bash ~/tools/cmp.sh /tmp/probes/$p.py $PWD; done
         14s bash   cat > /tmp/probes/p6d.py <<'EOF' class B:     def __init__(self, v, boom):         self.v = v         self.boo
         11s bash   python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/python/pkg-v12/pyboxed2.py') s=p.read_text() old

## review 0
[model opencode/deepseek-v4.1-flash-free]
Reviewed commit `6db9cf3` (pre28). The diff changes `_any_all` in `pyboxed2.py`, adds `ail_truthy_chk` to `cruntime.py`/`dunderrt.py`, plus test/manifest/docs.

**Probes** (HEAD, general `g` and default `d`; `/tmp/rprobes/`)
- `r1_positions.py`: match on both builds; base differs (p6 fixed).
- `r2_len.py`: HEAD propagates `__len__`/`__bool__`/inherited exceptions; `__bool__` returning a non-bool still prints `True` (pre-existing, base same).
- `r3_shortcircuit.py`: **DIFF** — fused `any(x for x in g())`/`all(x for x in h())` loses the generator's `finally` output.
- `r4b_exceptions.py`: match.
- `r5_plain.py`: match (base also match).
- `r6_gen_cleanup.py`: **DIFF** — early-exit and exhausted generator-function iterables lose `cleanup`; base matched CPython for these cases.
- `r7_bool_finally.py`: results now match CPython, but fused generator cleanups are missing.
- Worker probes: `p6/p6c/p6d` match; `p7/r89` still differ; `r15` matches. Verified.
- `gdev/g04_004`, `g09_018`: match on both builds. Verified.
- Non-user program: base/HEAD executables byte-identical (`sha256 5134e1…`), so no behavioural change there.
- Tests: `test_ail_pre28`, `test_ail_safetynet` → 2 modules, 0 failed (122 s). `update_manifest.py --check` → 0.
- Speed: `perf_event_paranoid=4`, so `icount` unavailable; used wall clock (below).

**Claims**
- Commit/files, p6 fix, p6/p6c/p6d results, p7/r89/r15 status, tests, manifest: verified (the two extra test modules were not re-run).
- “No added per-element cost”: **false** (see defect 2).
- “Matching CPython” for the fused path: **false** (see defect 1).

**Pre-existing**: non-bool `__bool__` TypeError; p7 eager inner genexpr; non-fused `any(gen)` missing generator cleanup; cleanup lost when the element expression itself raises.

**Unverified**: `test_ail_files`, `test_ail_corpus_findings3` (not re-run per instructions); exact generated C text (binaries compared instead).

VERDICT: FIX
1. Fused generator-expression short-circuit does not close a generator-function iterable, so `finally` side effects disappear. Probe `/tmp/rprobes/r3_shortcircuit.py` (`any(x for x in g())` with `g` having `finally: print("g cleanup")`): CPython prints `g cleanup` then `genfunc any True log []`; HEAD prints only `genfunc any True log []`. Base printed both, so this is introduced by the change. `/tmp/rprobes/r6_gen_cleanup.py` shows the same for `any(x for x in g() if x == 3)` (expected `cleanup` before `last deciding True`) and for the exhausted case.
2. Non-fused `any`/`all` over primitives in a class program now calls `ail_dun_truthy_chk` (marked `noinline`) once per element, whereas the old `ail_truthy_u` inlined the non-instance path. Probe `/tmp/rprobes/bench.py` (20 × `any([0]*1_000_000)` and `all([1]*1_000_000)`, forced general): base `0.43 s`, HEAD `0.49 s` (~14% slower, consistent over 5 runs). A fast inline path for `x.tag != AIL_T_INST` would avoid this.
[cost $0.0000, opencode tokens {"total": 2043615, "input": 101795, "output": 9637, "reasoning": 26007, "cache.write": 0, "cache.read": 1906176}]
    tool time: bash 5.1 min
        124s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre28 test_ail_safetynet > /tmp/rprobes/tests.lo
         40s bash   for p in p6 p6c p6d p7 r89 r15; do echo "===== HEAD $p ====="; bash ~/tools/cmp.sh /tmp/probes/$p.py "$PWD"; d
         37s bash   for p in /tmp/rprobes/*.py; do echo "===== HEAD $(basename $p) ====="; bash ~/tools/cmp.sh "$p" "$PWD"; done >
         20s bash   for p in /tmp/rprobes/r1_positions.py /tmp/rprobes/r5_plain.py; do echo "===== BASE $(basename $p) ====="; bas
         14s bash   for p in /tmp/rprobes/r2_len.py /tmp/rprobes/r3_shortcircuit.py; do echo "===== BASE $(basename $p) ====="; ba
         13s bash   cat > /tmp/rprobes/r4b_exceptions.py <<'EOF' class B:     def __init__(self, v, boom):         self.v = v     
         12s bash   cat > /tmp/rprobes/r7_bool_finally.py <<'EOF' class B:     def __init__(self, v, boom):         self.v = v    
         12s bash   for p in ~/corpus/gdev/g04_004.py ~/corpus/gdev/g09_018.py; do echo "===== HEAD $(basename $p) ====="; bash ~/

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Committed `c0f49a7` on `job-pre28-10240900`.

**Fixes**
- Fused `any`/`all` generator-expression path: when an iterable is a program generator call (`g()`, `o.m()`), materialise elements first so `finally` cleanup runs, then scan with early stop. Other iterables keep the fused path.
- `ail_truthy_chk`: inline `x.tag != AIL_T_INST` fast path; only instances use the noinline checked helper.

**Probes** (`bash ~/tools/cmp.sh … $PWD`, both builds)
- `pre28b_fused_gen_cleanup.py`, `pre28c_bool_positions.py`: match CPython.
- `p6`, `p6c`, `p6d`, `r15`, `r1_positions`, `r4b_exceptions`, `r5_plain`: match.
- `r3`/`r6`/`r7`: all fused generator-cleanup cases now match; remaining diffs are the pre-existing non-fused `any(gen)` cleanup and cleanup lost when the element expression itself raises.
- `p7`, `r89`, `r2_len` non-bool `__bool__`: still pre-existing diffs.

**Speed** `bench.py` general build: 0.41–0.42 s (base 0.43, previous HEAD 0.49).

**Tests** `test_ail_pre28 test_ail_safetynet test_ail_files test_ail_corpus_findings3` → 4 modules, 0 failed, 253 s. `update_manifest.py --check` → exit 0.
[cost $0.0000, opencode tokens {"total": 2598692, "input": 79918, "output": 11880, "reasoning": 17294, "cache.write": 0, "cache.read": 2489600}]
    tool time: bash 8.1 min
        255s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre28 test_ail_s
         72s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/p6.py /tmp/probes/p6c.py /tmp/probes/p6d.py /tmp/pr
         33s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check; echo "manifest $?"; for p in /
         21s bash   cd /home/runner/work/ail-ci/ail-ci && for p in r3_shortcircuit r6_gen_cleanup r7_bool_finally; do echo "===== 
         21s bash   cd /home/runner/work/ail-ci/ail-ci && for p in r3_shortcircuit r6_gen_cleanup r7_bool_finally; do echo "===== 
         21s bash   cd /home/runner/work/ail-ci/ail-ci && for p in r3_shortcircuit r6_gen_cleanup r7_bool_finally; do echo "===== 
         21s bash   cd /home/runner/work/ail-ci/ail-ci && for p in r3_shortcircuit r6_gen_cleanup r7_bool_finally; do echo "===== 
         21s bash   cd /home/runner/work/ail-ci/ail-ci && for p in r3_shortcircuit r6_gen_cleanup r7_bool_finally; do echo "===== 

## review 1
[model opencode/deepseek-v4.1-flash-free]
**Defect (change-caused, not pre-existing)**

1. Fused `any`/`all` genexpr over a generator reached indirectly no longer runs its `finally`. `_is_generator_call` recognises only a literal `f(...)`/`o.m(...)`; a generator arriving through an argument, local, attribute, dict value, list item or function alias keeps the early-`goto` fused path, which leaves it open. The base fused path eagerly exhausted it, so this is a regression. Probe `/tmp/rprobes/gen_alias3.py`:

```python
def g(tag):
    try:
        yield 1
    finally:
        print("cleanup", tag)

def take(it):
    return any(x for x in it)

def take_all(it):
    return all(x for x in it)

class Holder:
    def __init__(self, it):
        self.it = it

def main():
    print("any arg", take(g("any")))
    print("all arg", take_all(g("all")))
    h = Holder(g("attr"))
    print("attr", any(x for x in h.it))
    d = {"k": g("dict")}
    print("dict", any(x for x in d["k"]))
    xs = [g("item")]
    print("item", any(x for x in xs[0]))

main()
```

CPython (and base for the first four lines):
```
cleanup any
any arg True
cleanup all
all arg True
attr True
dict True
item True
cleanup attr
cleanup dict
cleanup item
```
HEAD (both `g` and `d`):
```
any arg True
cleanup all
all arg True
attr True
dict True
item True
```
`cleanup any` is missing; the trailing cleanups are missing too. `take(g(...))` is the clean regression: base matched CPython exactly there. The direct-call cases (`any(x for x in g())`, `o.m()`) do match.

**Verified claims**
- `p6`, `p6b`, `p6c`, `p6d`: same stdout as CPython on both builds.
- `r3`/`r6`/`r7`: remaining diffs are only the non-fused `any(gen)` close and cleanup lost when the element expression raises; both same on base (pre-existing).
- `r89`: diff identical on base (pre-existing).
- Direct-call generator cleanup (`pre28b`) is covered and passes.
- Speed: `/tmp/rprobes/bench.py` general build 0.41–0.42 s vs base 0.43 s, as reported.
- `test_ail_pre28 test_ail_safetynet` → 2 modules, 0 failed (122 s); `update_manifest.py --check` → 0.
- Commit/files and `Co-Authored-By` line verified.

**False claim**
- "all fused generator-cleanup cases now match": false for indirect generator iterables (defect 1).

**Pre-existing**
- `p7` eager inner genexpr; `r89` unclosed non-fused generator; cleanup lost when the element expression itself raises; non-bool `__bool__` (`r2_len`).
- `r15`/`r1`/`r4b`/`r5`, `test_ail_files`, `test_ail_corpus_findings3`, and non-feature `--debug-dir` C comparison: not re-run (unverified).

VERDICT: FIX
[cost $0.0000, opencode tokens {"total": 1051891, "input": 49396, "output": 4450, "reasoning": 19997, "cache.write": 0, "cache.read": 978048}]
    tool time: bash 4.2 min
        124s bash   date && cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre28 te
         30s bash   date && cd /home/runner/work/ail-ci/ail-ci && for p in p6 p6b p6c p6d; do echo "===== $p HEAD"; bash ~/tools/c
         21s bash   cd /home/runner/work/ail-ci/ail-ci && for p in r3_shortcircuit r6_gen_cleanup r7_bool_finally; do echo "===== 
         21s bash   cd /tmp/base && for p in r3_shortcircuit r6_gen_cleanup r7_bool_finally; do echo "===== $p BASE"; bash ~/tools
         12s bash   cd /home/runner/work/ail-ci/ail-ci && for p in gen_alias3 gen_alias4; do echo "===== $p HEAD"; bash ~/tools/cm
         12s bash   cd /tmp/base && for p in gen_alias3 gen_alias4; do echo "===== $p BASE"; bash ~/tools/cmp.sh /tmp/rprobes/$p.p
          8s bash   cd /tmp && mkdir -p benchn && cp /tmp/rprobes/bench.py benchn/bench.ail && cd benchn && for wt in /home/runner
          6s bash   cd /home/runner/work/ail-ci/ail-ci && bash ~/tools/cmp.sh /tmp/rprobes/gen_alias.py $PWD 2>&1 | tail -40

FINAL VERDICT: FIX  2026-10-24T00:47:57Z
