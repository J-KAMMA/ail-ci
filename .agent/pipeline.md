# job job-ffre1-11061046  started 2026-11-06T01:47:00Z  worker=chain reviewer=chain (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done. Commits `bfea307`, `232e4b0`, `f1a7685` on `job-ffre1-11061046` (not pushed; standing rules forbid push/PR).

- **8/8 workloads:** AIL digests equal CPython, all builds typed.
- **w3:** CPython prints the exact 25-digit sum; AIL stops loudly with `OverflowError` after printing the matching digest, in both default and `AIL_UNIFIED_FORCE=1` builds.
- **Slowest:** `w5_logline`, 0.831 s AIL vs 0.179 s CPython; ffre2 should start there.
- **Rust:** unavailable — no offline `regex` crate in `~/.cargo/registry` or a vendor directory.
- **icount:** unavailable — `perf_event_open` permission denied.
- **Texts:** deterministic, 21,113,572 B ASCII and 2,142,173 B mixed, identical across runs.

Tests: `test_ail_re` 16 OK; `test_ail_safetynet` 5 OK (needs >1.5 GB for `S4_generators_gc`, passes uncapped); `test_ail_files` 18 OK (1 skip); `test_ail_corpus_findings3` 2 OK; `update_manifest.py --check` clean. No CI shards run because the branch was not pushed.
[cost $0.0000, opencode tokens {"total": 4217883, "input": 131744, "output": 18147, "reasoning": 26904, "cache.write": 0, "cache.read": 4041088}]
    tool time: bash 24.5 min, write 0.0 min, edit 0.0 min, read 0.0 min
        348s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest -q test_ail_re 2>&1 | tail -20
        199s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest -q test_ail_files 2>&1 | tail -20 && ech
        134s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest -q test_ail_safetynet 2>&1 | tail -20
        125s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest -q test_ail_safetynet.GeneralPathSafetyN
        101s bash   cd /home/runner/work/ail-ci/ail-ci && python3 lab/regex/run.py > /tmp/ffre1-run2.log 2>&1; tail -50 /tmp/ffre1
         95s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'EOF' p='lab/regex/run.py' s=open(p).read() old='''    ascii
         92s bash   cd /home/runner/work/ail-ci/ail-ci && python3 lab/regex/run.py 2>&1 | tail -80
         92s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'EOF' p='lab/regex/run.py' s=open(p).read() old='''    sizes

## review 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Repo clean; no source edited. Here is my report.

## Review: lane ff-regex (lab/regex benchmark)

**What the change really does:** adds only `lab/regex/` — `gen_text.py` (seeded 20 MB ASCII + 2 MB mixed text), eight `w*.py` workloads, `run.py` (build, 5-run median, digest compare, optional icount), `RESULTS.md`, and `rust/README.md`. **No compiler/runtime changes**; `git diff --name-only work..HEAD` is all under `lab/regex/`, so C for any other program is untouched.

**Claims checked**
- 8/8 digests equal CPython, all builds `typed` — **verified** (`run.py --rounds 1 --out /tmp/...`): all eight report `typed match`.
- w3 prints matching digest then stops loudly in default *and* `AIL_UNIFIED_FORCE=1` — **verified** (exit 1, `OverflowError: integer overflow in int()`, digest line identical).
- Texts deterministic, 21,113,572 B / 2,142,173 B — **verified** (`gen_text.py` twice, `cmp` identical).
- `w5_logline` slowest — **verified** (rerun 0.769 s vs CPython 0.175 s).
- Rust unavailable — **verified** (`~/.cargo` has only `bin/`, `env`; no vendor dir).
- icount unavailable (`perf_event_open` denied) — **verified** (built `tools/icount.c`; probe returns Permission denied).
- `update_manifest.py --check` clean — **verified**.
- `test_ail_safetynet` passes — **verified** (149 s, 0 failed).
- `test_ail_re` 16 OK, `test_ail_files` 18 OK, `test_ail_corpus_findings3` 2 OK — **unverified** (not re-run; change adds/edits no test module).

**Probes** (`/tmp/rprobes`, `~/tools/cmp.sh`, general + default vs `python3`):
- `p1_digit_unicode` (Arabic-Indic `\d`) — same stdout both builds.
- `p2_int25` (25-digit `int()` literal) — refused by name (`int64 constant expression out of range`), acceptable.
- `p3_cafe` (`café[0-9]+` fullmatch/finditer on non-ASCII) — same stdout both builds.
- `p4_split` (`\s*,\s*` on empty/leading/trailing/double commas) — same both builds.
- `p5_sub` (group template, non-participating groups) — same both builds.

**Not met, disclosed and environmental (not defects):** Rust column and icount are `n/a` (no offline crate, perf denied); the 20 CI shards were not run because the branch was not pushed (task's own runner note forbids push). `w3` exits 1 vs CPython's 0 — explicitly permitted by the task ("stop loudly").

**Pre-existing:** none found.

Every claim the report makes was reproduced except the three unrelated test counts, which I did not re-run.

VERDICT: ACCEPT
[commandcode stop=end_turn turns=17 out_tokens=12118]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-06T05:27:20Z
