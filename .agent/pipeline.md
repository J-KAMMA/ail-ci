# job job-prog28-11021550  started 2026-11-02T06:55:06Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Committed on `job-prog28-11021550` (`833552b`, manifest pin `5686c7d`).

- Profiled all 8 programs; hot-function table and exact follow-ups in `lab/progfix/prog28.md`.
- Newly typed: `t141` (dict `max/min` key kind) and `g07_036` (enumerate-pair comprehension, named set literals). `t441`, `g04_012`, `g22_020` were already typed; `g25_040`, `t489`, `g01_002` are recorded follow-ups.
- Added/registered `test_ail_prog28.py` (6 tests, OK).
- Probes `/tmp/probes/prog28/p1`–`p5` match CPython on both builds.
- Tests: target suites 48 OK; safetynet/files/corpus_findings3 25 OK (1 skipped).
- All ten `lab/compare` generated C files are byte-identical to base; manifest `--check` passes.
[cost $0.1009, opencode tokens {"total": 13339752, "input": 209791, "output": 29170, "reasoning": 21111, "cache.write": 0, "cache.read": 13079680}]
    tool time: bash 22.7 min, edit 0.0 min
        565s bash   cd /home/runner/work/_temp/w2 && python3 -m unittest AIL_CURRENT.test_ail_safetynet AIL_CURRENT.test_ail_files
        222s bash   cd /home/runner/work/_temp/w2 && python3 -m unittest AIL_CURRENT.test_ail_prog28 AIL_CURRENT.test_ail_prog5 AI
        120s bash   mkdir -p /tmp/probes/prog28 && cat > /tmp/probes/prog28/p1_maxmin_dict_key.py <<'PY' class Box:     def __init
         85s bash   cd /home/runner/work/_temp/w2 && mkdir -p /tmp/prog28/cgen/cur /tmp/prog28/cgen/base && for t in $(ls lab/comp
         41s bash   cd /home/runner/work/_temp/w2 && for f in lab/census/programs/gdev/g25_040.py lab/corpus/programs/deepseek-v4.
         35s bash   cd /home/runner/work/_temp/w2 && AIL_NO_CACHE=1 python3 AIL_CURRENT/ail_chatgpt.py compile lab/census/programs
         24s bash   rm -f /tmp/prog28/out && mkdir -p /tmp/prog28/bins && cd /home/runner/work/_temp/w2 && for f in lab/census/pro
         21s bash   cd /home/runner/work/_temp/w2 && mkdir -p /tmp/prog28/hyb && for f in lab/census/programs/gdev/g25_040.py lab/

## review 0
[model opencode-go/deepseek-v4.1-flash]
## Review — prog28 typed reach

**What the change really does:** `python/pkg-v12/pyfunc.py` adds (a) key-kind inference for `max`/`min(..., key=)` over typed maps/lists/sets, (b) lowering of `[e for i, v in enumerate(X)]`, (c) treats container literals as non-numeric bindings, and (d) skips pre-binding a subscript of iterlower's synthesized holder. Plus test registration, DEVLOG, DIFFERENCES, program table.

**Probes** (`/tmp/rprobes`, HEAD and `git worktree` base `work`):
- `p1_def` (dict key max/min with int/None defaults) — same stdout; strict refuses by name.
- `p2_slice` (list[str] key via slice / attribute) — same; strict refuses (pre-existing gap).
- `p3_setstr` (set[str]/set[int] key) — same both builds.
- `p4_pair` (enumerate-pair over list/slice/range(start,stop)) — same; range(start,stop)/tuple variants refused by name.
- `p5_tupelt` (`[(i,v) ...]`) — same; strict refuses by name.
- `p6_multi_dict`, `p7_multi_list` (multi-arg `max/min(..., key=)`) — same; strict refuses by name.
- `p8_actual` (trim shape, strict) — builds typed, matches.
- `p9_step` (`enumerate(xs[::2])`, `xs[::-1]`) — same both builds.
- `p10_default_print` (default type mismatch printed directly) — same; strict refuses.
No probe produced different output, a crash, or a wrong exit status on HEAD that the base did not also have.

**Claims:**
- t141 and g07_036 newly typed — **verified**: both compile `--strict` rc=0; `test_ail_prog28` compares all t141 inputs and g07_036 with CPython, passes.
- `test_ail_prog28.py` added/registered, 6 tests OK — **verified** (`par_check -j 2 test_ail_prog28 test_ail_safetynet`: 2 modules, 0 failed).
- Ten `lab/compare` generated C byte-identical — **verified** on the ten `main.ail` sources (all `same`). The `main.py` variants of scar_life/tally_lang/tree_fold do not build on either base or HEAD (see Pre-existing).
- t441/g04_012/g22_020 already typed; profiling table numbers; exact follow-up messages; “48 OK / 25 OK (1 skipped)” — **unverified** (not re-run within the time box).
- Worker’s `/tmp/probes/prog28/p1–p5` results — not re-run, but independently covered by the probes above, which all matched.

**Pre-existing** (identical on base): `lab/compare/src/{scar_life,tally_lang,tree_fold}/main.py` are refused by name (re `.groups()`, tuple-shape compares, empty-tuple element typing); typed-path min/max-with-key gaps for non-Name list/set sources and multi-arg forms are refusals on both builds.

**Unverified:** full profiling figures, the three “already typed” programs, `test_ail_files`/`test_ail_corpus_findings3`, manifest `--check`, and exact follow-up refusal text.

VERDICT: ACCEPT
[cost $0.0237, opencode tokens {"total": 1144070, "input": 59973, "output": 6695, "reasoning": 12570, "cache.write": 0, "cache.read": 1064832}]
    tool time: bash 34.4 min
        762s bash   cd /home/runner/work/_temp/w2 && rm -rf /tmp/rgencur /tmp/rgenbase && mkdir -p /tmp/rgencur /tmp/rgenbase && f
        493s bash   cd /home/runner/work/_temp/w2 && rm -rf /tmp/rgencur /tmp/rgenbase && mkdir -p /tmp/rgencur /tmp/rgenbase && f
        338s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_prog28 test_a
        242s bash   cd /home/runner/work/_temp/w2 && for t in scar_life tally_lang tree_fold; do echo ===$t; rm -rf /tmp/gc_$t /tm
        171s bash   cd /home/runner/work/_temp/w2 && rm -rf /tmp/ailcur /tmp/ailbase && mkdir -p /tmp/ailcur /tmp/ailbase && for t
         29s bash   cd /home/runner/work/_temp/w2 && date && for p in /tmp/rprobes/p1_def.py /tmp/rprobes/p2_slice.py /tmp/rprobes
          9s bash   cd /tmp/rprobes && cat > p9_step.py <<'PY' def a(xs: list[int]) -> list[int]:     return [v for i, v in enumer
          9s bash   cd /tmp/rprobes && cat > p10_default_print.py <<'PY' def main() -> None:     d: dict[str, int] = {}     print(

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-02T12:17:27Z
