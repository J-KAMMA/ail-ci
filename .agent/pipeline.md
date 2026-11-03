# job job-pyreachs4-11040311  started 2026-11-03T18:11:48Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the review defect and committed on `job-pyreachs4-11040311`.

**Defect:** `rebinding._branch_kind_split` ignored non-`Name` bindings, so a branch with `except ValueError as x` could still be split, hiding Python's unbinding. It now skips a chain when any branch binds the name via `ExceptHandler.name`, import alias, `def`/`class` name, `global`/`nonlocal`, or a match pattern. The strict path refuses by name; default and unified builds match CPython.

**Probe** `/tmp/probes/r21min.py`:
- before: default exit 0, stdout `aa` (wrong)
- after: default/unified exit 1, empty stdout, `UnboundLocalError: cannot access local variable 'x' ...`
- strict: refused with `exception handler binding 'x' conflicts ...`

**Tests:** `test_ail_pyreach_unpack` 12 OK, `test_ail_safetynet` 5 OK, `test_ail_files` 18 OK (1 skip), `test_ail_corpus_findings3` 2 OK. `tools/update_manifest.py --check` exit 0.

Commits: `81eb0d7` (fix + regression test + DEVLOG), `afd1eaa` (match-pattern bindings).
[cost $0.0000, opencode tokens {"total": 816404, "input": 36066, "output": 4491, "reasoning": 4391, "cache.write": 0, "cache.read": 771456}]
    tool time: bash 11.0 min, edit 0.0 min
        234s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -B test_ail_corpus_findings3.py 2>&1 | tail -20
        172s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -B test_ail_safetynet.py 2>&1 | tail -20
        108s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -B test_ail_files.py 2>&1 | tail -20
         49s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -B test_ail_pyreach_unpack.py 2>&1 | tail -8
         48s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -B test_ail_pyreach_unpack.py 2>&1 | tail -20
         17s bash   cd /home/runner/work/ail-ci/ail-ci && bash ~/tools/cmp.sh /tmp/probes/r21min.py $PWD
         17s bash   cd /home/runner/work/ail-ci/ail-ci && bash ~/tools/cmpu.sh /tmp/probes/r21min.py $PWD
         10s bash   mkdir -p /tmp/probes && cat > /tmp/probes/r21min.py <<'EOF' def main():     if 1 == 1:         x = b"aa"      

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change really does:** `_branch_kind_split` now skips an if/elif chain when any branch binds the split name through a non-`ast.Name` node (`except ... as`, import alias, `def`/`class` name, `global`/`nonlocal`, match pattern), via a new `_branch_nonname_binds`; plus a regression test, DEVLOG and manifest update. Matches the report.

**Defect from last review — fixed.** `/tmp/rprobes/r21min.py` on HEAD: `d` and `g` exit 1, empty stdout, `UnboundLocalError: cannot access local variable 'x'…`; strict exits 3 with `exception handler binding 'x' conflicts…`. On `work` (reviewed HEAD) `d` exits 0 and prints `aa`, so the defect reproduces as reported.

**Probes (HEAD vs `work`):**
- `p2_else_except.py` (handler in `else` branch): HEAD both builds exit 1/empty stdout/UnboundLocalError = CPython; `work` default prints `aa` (wrong). Fix generalises.
- `p7_other_except_name.py` (handler binds `e`, so split must still happen): HEAD strict typed, output = CPython; not over-blocked.
- `p4_def_name.py`, `p5_import_alias.py`, `p6_match_bind.py`: HEAD both builds match CPython; `work` also matched, so these extra guards are conservative rather than demonstrably necessary. No regression.
- C bytes: `kind_split.py` and a plain if/elif/except program produce byte-identical `program.c` on HEAD vs `work`.

**Claims:** all verified — defect diagnosis, default/unified behaviour, strict named refusal, test counts (`test_ail_pyreach_unpack` 12 OK, `test_ail_safetynet` 5 OK, `test_ail_files`/`test_ail_corpus_findings3` 0 failed), and `update_manifest.py --check` exit 0.

**Pre-existing:** nothing new observed. The old typed-unpack message difference was not re-tested.

**Unverified:** ten-lab strict lists before/after, `.ail` C byte-identical gate (change is Python-syntax-only and C checks above are identical), tuple-call reachability, `AIL_IR=0`.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 579680, "input": 38705, "output": 4118, "reasoning": 15001, "cache.write": 0, "cache.read": 521856}]
    tool time: bash 9.8 min
        230s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_files test_ail_c
        178s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pyreach_unpack t
         77s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/p2_else_except.py /tmp/rprobes/p4_def_name.py /tmp
         69s bash   cd /tmp/base && for p in /tmp/rprobes/p2_else_except.py /tmp/rprobes/p4_def_name.py /tmp/rprobes/p5_import_ali
         18s bash   cd /home/runner/work/ail-ci/ail-ci && bash ~/tools/cmp.sh /tmp/rprobes/r21min.py $PWD 2>&1 | tail -30
         10s bash   cd /tmp/base && bash ~/tools/cmp.sh /tmp/rprobes/r21min.py $PWD 2>&1 | tail -30
          2s bash   cd /home/runner/work/ail-ci/ail-ci && for p in r21min p2_else_except p4_def_name p5_import_alias p6_match_bind
          1s bash   cd /tmp/base && for p in p4_def_name p6_match_bind r21min; do echo "== BASE strict $p"; AIL_NO_CACHE=1 AIL_NO_

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-03T19:47:49Z
