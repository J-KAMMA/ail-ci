# job job-cpyhyb2d-11080311  started 2026-11-07T18:12:31Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. Everything verified on the final commit.

## Result: LANDED

**Step 1** — integ lacked real work: the finished branch adds the hybrid builder changes, `lab/hybrid/`, DEVLOG and `ci-proposed/workflows/agent-worker.yml`, so NOCHANGE did not apply.

**What I did**
- Cherry-picked `aeac2bb9e` ("agent work") onto the job branch (parent = `origin/integ` `79bb37649`). Conflicts resolved in favour of integ; the job runner's `.agent/` infra and `corpus/gdev` kept (the pick wanted to delete them).
- `ail_chatgpt.py` / `program.c` untouched; no `.github` edits (`git diff HEAD~1 HEAD -- .github` empty).
- Commit `334192aca`, 7 files, +620/−10. Manifest regenerated, `update_manifest.py --check` clean.
- DEVLOG entry added at top, dated 2026-11-07.

**Tests** (final commit, `ulimit -v 2500000`, sequential)
- `test_ail_cpython_hybrid` 8/8 OK
- `test_ail_safetynet` 5/5 OK
- `test_ail_files` 18 OK (1 skipped)
- `test_ail_corpus_findings3` 2/2 OK

**40-program CPython check** — `lab/hybrid/check.py --json`: **40/40 match** (stdout, exit status, last stderr).

**Report numbers**
- Functions that went native across the 40 programs: **1** (`reverse_words` in `t079.py`).
- Functions kept on CPython, ranked: **a call can raise or have side effects 4**, **indexing can raise 2**, **division or power can raise 1** (7 candidates total).

**Probes** (`/tmp/probes/`, 12 programs)
- Hybrid build vs CPython, all `match=yes`: p1 int widths (int64 edges), p2 overflow, p3 empty/negative, p4 argument values, p5 list item, p6 attribute, p7 dict value, p8 aliasing, p9 empty string, p10 reasons, p11 float result, p12 mutating list.
- Builder boundaries: default output dir `<stem>_hybrid`, launcher runs and matches, `-o` same-dir guard leaves the source byte-identical, missing SOURCE refused by argparse.
- `cmp.sh` AIL builds (general + default): p1, p3–p9 same stdout; p2 (int64 overflow) is refused by name in both builds (`OverflowError: integer overflow in * ... --exact-int`), while the hybrid matches CPython.

Not verified: nothing claimed beyond these runs.
[commandcode stop=end_turn turns=44 out_tokens=21100]

## review 0
[model commandcode/deepseek-v4.1-flash]
I have what I need. Final report:

## Review: cpyhyb2d (land cpyhyb2b)

**What the change really does.** `AIL_CURRENT/ail_cpython_hybrid.py`: schema `1`→`2`; `build.json` gains `run_file`/`python_file`; the hybrid copy is now written as `<stem>_run.py` (launcher execs that) with the old `<stem>.py` kept as an extra copy unless it would be the source file; adds a standalone `__main__` CLI whose default output is `SOURCE.parent/<stem>_hybrid`. Plus `lab/hybrid/{check,measure}.py`, RESULTS.md, one test assertion, manifest, DEVLOG. No compiler/runtime change.

**Claims checked**
- 40/40 match CPython (`lab/hybrid/check.py --json`) — verified.
- 1 native function, `reverse_words` in `t079.py` — verified.
- Reasons: "call can raise/side effects" 4, "indexing can raise" 2, "division or power can raise" 1 (7) — verified exactly.
- `ail_chatgpt.py`/`program.c` untouched, no `.github`/`.agent` deltas — verified.
- `update_manifest.py --check` — clean.
- `test_ail_cpython_hybrid` 8/8, `test_ail_safetynet` 5/5 — the hybrid module passes (8 test methods); safetynet passes (case count not recounted).
- Probes: `-o` same dir leaves the source byte-identical (and base **overwrote** it — the guard is a real fix); default build, empty source, `my-prog.py`, and a source whose stem already ends in `_run` all build and run correctly; values stay CPython-correct after overwriting an adjacent data file and after list/bytearray/dict aliasing; `a1/a2` (`cmp.sh`) identical on HEAD and base; `--debug-dir` `program.c` byte-identical to base (only `native_report.json` temp paths differ); int64 overflow is refused by name identically on base and HEAD → pre-existing, not caused by this change.

**Report inaccuracies (documentation only, non-blocking)**
- DEVLOG says `test_ail_cpython_hybrid` "passes 7/7"; the module has 8 tests and all 8 pass (worker report says 8/8).
- The report says the branch adds `ci-proposed/workflows/agent-worker.yml`; it was already in base and the landed diff does not touch it.
- `docs/design/CPYTHON_HYBRID.md` still documents the launcher as `DIR/prog.py`; it now runs `DIR/prog_run.py`, and with `-o` equal to the source dir `prog.py` is intentionally not written — the design doc is stale.

**Pre-existing.** `cmp.sh` int64-overflow refusal (`OverflowError: integer overflow in * ... --exact-int`) is identical on base. Overwriting an unrelated `<stem>.py` present in `-o DIR` (probe out5) also happens on base.

**Unverified.** `test_ail_files` and `test_ail_corpus_findings3` (outside reviewer scope; not re-run), `lab/hybrid/measure.py` (not exercised). No speed check: the change touches no compiler/runtime code and the generated C is unchanged.

VERDICT: ACCEPT
[commandcode stop=end_turn turns=22 out_tokens=20704]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-07T19:53:36Z
