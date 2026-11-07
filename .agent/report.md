# job job-rundiff1_rr1-11070701  started 2026-11-06T22:02:15Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
(no final text)
[commandcode stop=? turns=? out_tokens=?]
[model opencode-go/deepseek-v4.1-flash]
(no final text)
[cost $0.0000, opencode tokens {}]
    tool time: 

## review 0
[model commandcode/deepseek-v4.1-flash]
# Review — rundiff1 (`ail run --diff`)

**What the change really does:** adds a `--diff` mode to `cmd_run` in `packaging/ail_lang/cli.py` that builds as `ail run` does, streams the native program live, runs `python3 prog.py` with captured output on a shared stdin temp file and the same cwd/args/env/timeout, then reports agree / DIFFER / loud-stop / timeout with exit 0-or-program / 3 / 4 / 124. No compiler or runtime files are touched (the C of any program is unchanged by construction). The worker produced **no final report text**; I checked the DEVLOG/docs claims instead.

**Probes (all in /tmp/rprobes/, run against HEAD; base /tmp/base where relevant):**

| probe | result |
|---|---|
| p1 stdin+args, p2 empty, p3 unicode/no-trailing-newline, p4 3 000-line stdout, p5 exit 5, p6 IndexError, p8 stderr noise, p10 partial stdin, p11 print-then-raise | `agree`, correct exit (0/5/1) — matches CPython |
| p7 int64 overflow | `loud stop by design: OverflowError: integer overflow in *`, exit 4 |
| p9 slow `--timeout 1` / fake-slow `--python` | `timeout: native` / `timeout: cpython`, exit 124 |
| fake interpreters (different line, prefix, exit 2, long line, wrong exception) | `DIFFER: stdout line 1/2`, `DIFFER: exit code 0 vs 2`, `DIFFER: exception IndexError vs TypeError`, exit 3, 200-char truncation |
| `--json` agree/differ/no-trailing-newline | one JSON object with the documented keys, exit codes |
| stdin reuse (full and partial reads) | both runs see the same bytes — verified, no buffer aliasing |
| `--timeout=N`, `--python=PATH`, `prog.py --diff`, `--strict` | OK |
| **value-taking compiler options** | **`ail run --diff -I . p.py`, `--syntax python`, `--debug-dir DIR` all exit 2 with the project usage; base `ail run -I . p.py` / `--syntax python p.py` exit 0 and run** |

**Tests:** `test_ail_rundiff` ok 24.9 s, `test_ail_safetynet` ok 374.6 s, 0 failed; `update_manifest.py --check` exit 0.

**Claims:** implementation, outcomes/exit codes, loud-stop table, shared stdin, live native output, `--json` shape, exception-type-only compare, `ail run` unchanged without `--diff`, `prog.py --diff` to the program — verified. Census rows spot-checked (first 10 corpus `agree`; `g01_008` differ, `g01_020`/`g01_032`/`g02_010` loud stops match RESULTS.md) — verified. The docs statement "options before [the source] go to the compiler" is **false for `--diff`** (see defect).

**Pre-existing (also on base, not blocking):** `ail run -- prog.py` reports "usage" instead of taking `prog.py` after `--`.

**Unverified:** the full 30-case `lab/compare` census and the remaining 40 corpus rows (spot-checked only); interactive-TTY stdin path; very large stderr.

## Defects
1. `_split_diff` drops the *value* of every two-word compiler option (`-o/--output`, `-I`, `--module`, `--module-path`, `--object`, `--syntax`, `--target`, `--debug-dir`, `--link`, `--lib`), so the option is left dangling and `_split_source` no longer finds the source file. Probe `/tmp/rprobes/p2_empty.py`: `ail run --diff -I . p2_empty.py` (also `--syntax python p2_empty.py`, `--debug-dir /tmp/dd p2_empty.py`) → **actual** exit 2, only `usage: ail run prog.py ...`; **expected** the program runs and `ail diff: agree`, exit 0 — which is what the base `ail run -I . p2_empty.py` / `ail run --syntax python p2_empty.py` does. Fix: append the option's value to `kept` as well (or copy the whole pre-source slice minus the diff options).

VERDICT: FIX
1. `packaging/ail_lang/cli.py:_split_diff` drops option values; `ail run --diff -I . prog.py` (and `--syntax`, `--debug-dir`, `-o`, …) exits 2 with the usage line, while `ail run` with the same option runs (exit 0). Probe `/tmp/rprobes/p2_empty.py`.
[commandcode stop=end_turn turns=33 out_tokens=23563]

## worker report 1
[model commandcode/deepseek-v4.1-flash]
Fixed the review defect and committed on `job-rundiff1_rr1-11070701` (a30063f). Not pushed, per the run rules.

**Defect 1 — `_split_diff` dropped option values.** `packaging/ail_lang/cli.py` now copies a two-word compiler option together with its value (`-I .`, `--syntax python`, `--debug-dir DIR`, `-o OUT`, …), and detects `--diff` in the same scan instead of a membership test, so a value is never mistaken for the mode. Docs (`docs/CLI.md`) say which pre-source words go to the build; a regression test covers `-I .`, `--syntax python`, `--debug-dir DIR`. DEVLOG note added; manifest pins regenerated (`--check` clean).

**Probes (`/tmp/probes/`, final commit):**

| probe | result |
|---|---|
| `run --diff -I . p_opt_basic.py one two` (stdin) | agree, exit 0, output matches CPython |
| `run --diff --syntax python ...` | agree, exit 0 |
| `run --diff --debug-dir <fresh> ...` | agree, exit 0 (base with same fresh dir: exit 0) |
| `run --diff -o OUT ...` | agree, exit 0 |
| `p_opt_empty.py` with `-I .` | agree, exit 0 |
| `p_opt_exit.py` (exit 5) with `-I .` | agree, exit 5 |
| `p_opt_diff.py --diff x` with `-I .` | agree; `--diff` after source still reaches the program |
| `run --diff -- p.py` | exit 2, same as base `run -- p.py` (pre-existing, unchanged) |
| cmp.sh on all 4 probes, both builds (`g`,`d`) | same stdout/exit as CPython |

One probe artifact: reusing an already-existing `--debug-dir` makes both base and diff refuse (exit 2 / loud stop); with fresh dirs both run and agree.

**Tests (final commit):** `test_ail_rundiff` + `test_ail_safetynet` + `test_ail_files` + `test_ail_corpus_findings3` → 39 tests, OK (1 skip), exit 0. Earlier CLI group (packaging, project, debug, sdk, c_export, scan_spec_modes, ffi_callbacks, cli_args) → 111 tests, one flake in `test_ail_packaging.test_build_is_reproducible` caused by concurrent wheel builds; it passes when rerun alone (2.6 s) and is untouched by this change.
[commandcode stop=end_turn turns=53 out_tokens=19465]

## review 1
[model commandcode/deepseek-v4.1-flash]
Time check: I started at 00:15 and it is now ~00:52, so I'm stopping probes here and writing up.

## What the change really does

Beyond the reported fix, `git diff work..HEAD` adds the whole feature: a `--diff` mode in `packaging/ail_lang/cli.py` (`_split_diff`, `_diff_run`, `_diff_verdict`, `_diff_report`, `_diff_build_failed`, `LOUD_STOPS`), `docs/CLI.md`, `test_ail_rundiff.py` (+ registration), `lab/rundiff/*`, DEVLOG. The last commit `a30063f` is the reported fix: `_split_diff` now keeps a two-word compiler option **and its value** and detects `--diff` in the same scan. That part is correct and verified.

## Defect

The build-failure classifier reports **any** unrecognised build stop as `loud stop by design` (exit 4) whenever CPython ran the program, not just AIL's documented loud errors. The task says exit 4 is for "one of AIL's documented loud errors … list the recognised messages in one table"; a broken link or a bad option is not one of them, and exit 3 is "reserved" for a difference. A real toolchain/compiler breakage is therefore mislabelled as "by design" — the exact failure class the command exists to surface.

Probe 1 — `/tmp/rprobes/p_agree.py` (reads stdin, echoes argv; CPython exits 0):
```
ail run --diff --link /nonexistent/libnope.so p_agree.py   (stdin empty)
```
- expected: `DIFFER` (no native program, the build stopped), exit 3
- actual: `ail diff: loud stop by design: the C compiler rejected this:` , exit 4 (CPython's `read 0` was fine). The "reason" is the driver's banner line, not a cause.

Probe 2 — same program:
```
ail run --diff -I /nonexistent/dir p_agree.py
```
- expected: exit 3 (difference) or exit 2 (usage), not a language limit
- actual: `ail diff: loud stop by design: each --module-path must name an existing directory`, exit 4

`docs/CLI.md` codifies this wrong rule ("Any other build stop is `loud stop by design` when CPython runs the program fine"), so code and docs agree with each other but not with the task.

## Verified (agree with the report)

- Two-word option values now reach the build: `--diff -I .`, `--diff --syntax python`, `--diff --debug-dir DIR`, `--diff -o OUT` all `agree`, exit 0; `-I`-less base exit 2 was the old bug.
- `--diff` detection: `run --diff … prog.py --diff` hands `--diff` to the program (`arg --diff`, agree); `run --diff --` and `run --diff --cc tcc` behave exactly as base (pre-existing).
- `ail run` without `--diff` unchanged: plain run, `--strict --json`, stdin/argv — same as `/tmp/base`; generated C identical (`--debug-dir` A/B diff empty).
- Modes: agree (with stdin/args/base exit code 5), stdout DIFFER (line N, both lines), exception type only (IndexError both → agree, exit 1), exit-code DIFFER, `--json` shape (agree/differ/loud/timeout, `line` null, `seconds` pair, own line after non-newline output), `--timeout 1` → `timeout: native` 124 and `timeout: cpython` 124, `--python` name/path/`=value`, `--timeout=0`/`-3`/`soon` refused with exit 2, int64 overflow → loud stop exit 4, `--exact-int` agree, project mode (`ail.toml` entry) agree.
- Tests: `test_ail_rundiff` ok (12.4 s), `test_ail_safetynet` ok (192.9 s), `test_ail_files` ok, `test_ail_corpus_findings3` ok; `tools/update_manifest.py --check` clean.
- Census spot-check: `corpus/gdev/g01_008.py` really differs (`native ''` vs `'Parsed entries: 6'`).

## Unverified / pre-existing

- Census counts 17/4/9 and 46/1/3: only the one spot-check above was reproduced; the table as a whole is unverified.
- `--cc tcc`, `-- p.py`, `--link` failure exit code: identical on `/tmp/base` — pre-existing, not caused here.
- Speed: CLI-only change, no hot code touched, so no icount run.

VERDICT: FIX
1. `_diff_build_failed` treats every build stop where CPython succeeded as `loud stop by design` (exit 4) instead of only the `LOUD_STOPS` table. Probe `/tmp/rprobes/p_agree.py` with `ail run --diff --link /nonexistent/libnope.so p_agree.py`: expected a `DIFFER`/exit 3 (unrecognised build failure — a compiler/toolchain defect, which this command must not call "by design"), actual `ail diff: loud stop by design: the C compiler rejected this:` exit 4. Same for `-I /nonexistent/dir` (actual exit 4, expected 3 or 2). Fix: gate the exit-4 path on `_loud_stop(..., "build")` and report other build stops as differences; update the docs sentence that blesses the current rule.
[commandcode stop=end_turn turns=31 out_tokens=149397]

FINAL VERDICT: FIX  2026-11-07T00:52:55Z
