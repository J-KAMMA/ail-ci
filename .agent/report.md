# job job-pre54-10241243  started 2026-10-24T03:43:52Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
**Result:** `z_intmin` reproduced on both builds (`integer overflow`, CPython prints three `9223372036854775808` lines). Since AIL's `int` is int64, `abs`/unary `-`/`* -1` at `INT64_MIN` cannot match CPython, so the constant `round()` at the boundary is now refused by name at compile time in `pyc.build` for both builds.

Commit: `5db3a11` (7 files). Records updated: DEVLOG (root and AIL_CURRENT), DIFFERENCES `C?-job-pre54-10241243-1`, manifest check passes.

**Probes** (`cmp.sh`, g = general, d = default):
- `z_intmin` (abs, `-x`, `x * -1`): refused by name, both builds
- `z_intmin_round_only`: refused by name, both builds
- `z_intmin_containers` (list item): refused by name, both builds
- `z_intmin_positive` (`round(2**63)`): refused by name, both builds
- `z_intmin_near` (argument/list/attribute/dict, just inside boundary): CPython match, both builds
- `z_intmin_two_arg` (`round(x, 0)`, float result): CPython match, both builds
- `z_intmin_shadowed` (user-defined `round`): CPython match, both builds
- `z_intmin_int_arg`: still hits the pre-existing out-of-range int literal refusal, unchanged

**Tests on final commit** (`par_check.py -j 2`): `test_ail_pre54`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed (158 s).
[cost $0.0000, opencode tokens {"total": 3475777, "input": 216051, "output": 9083, "reasoning": 21843, "cache.write": 0, "cache.read": 3228800}]
    tool time: bash 7.1 min
        210s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_safetynet test_ail_files test_ail_corpus_finding
        159s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre54 test_ail_safetynet test_ail_files test_ail
         24s bash   mkdir -p /tmp/probes cat > /tmp/probes/z_intmin.py <<'EOF' x = round(-9223372036854775808.0) print(type(x).__n
         21s bash   git add AIL_CURRENT/test_ail_pre54.py AIL_CURRENT/ail_check.py AIL_CURRENT/python/pkg-v12/pyc.py && python3 to
          4s bash   mkdir -p /tmp/probes && cat > /tmp/probes/z_intmin.py <<'EOF' x = round(-9223372036854775808.0) print(type(x).
          2s bash   python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/python/pkg-v12/pyc.py') s=p.read_text() s=s.repl
          0s bash   python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/ail_check.py') s=p.read_text() old="    'test_ai
          0s bash   pwd && ls -la && git status && git branch --show-current && git log --oneline -5

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Change.** `pyc.build` now pre-parses the source and raises a named `Unsupported` for a one-argument `round()` whose argument folds to a float with `|v| >= 2**63`, unless the module binds/imports/parameterizes `round` anywhere. Plus `test_ail_pre54.py`, DEVLOG and a DIFFERENCES row. This matches the report, though the report omits how broad the refusal is and that only literal/unary constant folding is covered.

**Probes** (`cmp.sh`, both builds; base = `/tmp/base`):

| probe | result |
|---|---|
| `z_intmin` (abs, `-x`, `x*-1`) | base g/d `integer overflow`; HEAD both refused by name → fixed |
| `round_only` (`print(x)` only) | base matches CPython; HEAD refuses → new refusal of a previously-correct program (allowed by task's "refuse the construct") |
| `p8` comparison-only at boundary | base d matches; HEAD refuses (same as above) |
| `near` (-2**63+1024, +2**63-1024, abs/-/*-1) | HEAD both match CPython |
| 2-arg `round(x, 0)` | HEAD both match |
| shadowed `def round` | HEAD both match; not refused |
| list/attribute/dict boundary | refused by name, both builds (test module) |
| `round(-2.0**63)` | identical on base and HEAD: `integer overflow` (expression not folded) |
| `round(-9223372036854775808)` int arg | identical on base/HEAD: int literal refusal |
| nan/inf | general matches; default `round() of nan` exit 1, identical to base |
| unrelated program, `--debug-dir` | `program.c` byte-identical to base; same executable output |

**Claims.** Reproduced base `z_intmin` (three `9223372036854775808` lines in CPython) — verified. Refusal on both builds — verified. Near/two-arg/shadowed/container cases — verified via probes and `test_ail_pre54`. Int-arg unchanged — verified. `z_intmin_positive` refused — verified. "7 files", DEVLOG, DIFFERENCES row, `update_manifest.py --check` (rc 0) — verified.

**Tests.** `test_ail_pre54 test_ail_safetynet test_ail_files test_ail_corpus_findings3`, `-j 2`: 4 modules, 0 failed, 157 s — matches the report.

**Pre-existing** (identical on base, not blocking): default-build nan/inf `round()`; `round(1e19)` failing both builds (HEAD now refuses instead); any parameter/binding named `round` anywhere disables the refusal (`p7` still overflows); `round(-2.0**63)` still overflows; int-literal boundary refusals. Speed: no runtime change, generated C is identical; only an extra compile-time `ast.parse`.

**Unverified:** gdev instruction counts (not needed given byte-identical C); exhaustive shadowing variants.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 437324, "input": 32199, "output": 3894, "reasoning": 15567, "cache.write": 0, "cache.read": 385664}]
    tool time: bash 3.7 min
        158s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre54 test_ail_s
         18s bash   cat > /tmp/rprobes/p5_inside.py <<'EOF' x = round(-9223372036854774784.0) print(type(x).__name__, x, abs(x), -
         13s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/p*.py; do echo "=== HEAD $p ==="; bash ~/tools/cmp
         10s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/z_intmin_positive.py /tmp/probes/z_intmin_round_onl
          8s bash   cd /tmp/base && for p in /tmp/rprobes/p0_z.py /tmp/rprobes/p2_naninf.py /tmp/rprobes/p4_print.py; do echo "===
          6s bash   cat > /tmp/rprobes/p12_line.py <<'EOF' print("start") x = round(-9223372036854775808.0) print(abs(x)) EOF cd /
          5s bash   cat > /tmp/rprobes/p13_int.py <<'EOF' x = round(-9223372036854775808) print(abs(x)) EOF cat > /tmp/rprobes/p14
          2s bash   cat > /tmp/rprobes/p15_plain.py <<'EOF' xs = [1, 2, 3] t = 0 for v in xs:     t += v * 2 print(t, len(xs), xs[

FINAL VERDICT: ACCEPT  2026-10-24T04:02:13Z
