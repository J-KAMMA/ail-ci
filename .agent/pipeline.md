# job job-bces4-11051929  started 2026-11-05T10:29:42Z  worker=chain reviewer=chain (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed both review defects in `fieldfacts.py`:

- `bytes_fields` now holds unambiguous bytes **field** names, not struct names; `n_bytes_collide.ail` dumps `nonneg: []` (prints `-5`).
- `_field_still_nonneg` now scans every `Store`/`Del` attribute form; tuple/chained/`for`/`with`/comprehension/`del` stores retire the fact. `n_tuple.py` dumps `nonneg: []` (prints `-1`).

Added regression cases to `test_ail_bce.py`. `test_ail_bce` 6/6, `test_ail_safetynet` 5/5, `update_manifest.py --check` pass. No generated C changes. Committed as `b3a5b9c`.
[cost $0.0000, opencode tokens {"total": 2732472, "input": 96682, "output": 9415, "reasoning": 14151, "cache.write": 0, "cache.read": 2612224}]
    tool time: bash 7.3 min, edit 0.0 min, read 0.0 min
        241s bash   cd AIL_CURRENT && ulimit -v 1500000; python3 -B -m unittest test_ail_bce test_ail_safetynet 2>&1 | tail -30
        172s bash   cd AIL_CURRENT && python3 -B -m unittest -v test_ail_safetynet 2>&1 | tail -25
         11s bash   cd AIL_CURRENT && python3 -B -m unittest -v test_ail_bce.FieldFactsTests 2>&1 | tail -40
          4s bash   cd /tmp/probes && cat > n_chained.py <<'EOF' class R:     def __init__(self, pos: int) -> None: self.pos = pos
          2s bash   mkdir -p /tmp/probes && cat > /tmp/probes/n_bytes_collide.ail <<'EOF' struct vals { data: bytes; } struct R { 
          1s bash   cd /tmp/probes && rm -f n_bytes_collide.ail.out n_bytes_collide.ail.facts.json n_tuple.py.out n_tuple.py.facts
          1s bash   cd /tmp/probes && cat > n_method_pos.py <<'EOF' class R:     def __init__(self, pos: int) -> None: self.pos = 
          1s bash   python3 tools/update_manifest.py && python3 tools/update_manifest.py --check && git status --short

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review

**What the change really does:** rewrites `bytes_fields` in `fieldfacts.py` to hold unambiguous bytes *field* names (not struct names), and replaces `_field_still_nonneg`'s recognition of `Assign`/`AnnAssign`/`AugAssign` with a scan of every `Store`/`Del` attribute for the field that retires the fact on any unclassified target form. Adds regression cases, manifest hashes and a DEVLOG entry. Matches the report.

**Claims checked**
- Bytes collision fixed: **verified** — `n_bytes_collide.py` and the review's exact `.ail` both dump `{"groups": [], "nonneg": []}` and print `-5`; base keeps `[["R","pos"]]`.
- Real bytes index still counts: **verified** — `r.data[0]` fact `[["R","pos"]]`, prints `97` in both builds.
- Unknown store forms retire: **verified** — tuple, chained, `for`, `with`-body, alias, dict-item, list-item and a tuple store inside a method all give `nonneg: []` on HEAD (method case still `[["R","pos"]]` on base). `del`, comprehension targets and `with ... as r.pos` are refused by name (acceptable). `r.pos *= -1` retires.
- No generated C change: **verified** — `program.c` byte-identical HEAD vs `/tmp/base` for a non-feature program, `n_bytes_collide` and `bytes_positive`; ledger C identical size; nothing reads `facts['fields']`.
- Tests: **verified** — `par_check -j 2 test_ail_bce test_ail_safetynet` green (176 s); module test counts 6 and 5 as reported.
- Manifest `--check`: **verified** (rc 0); commit `b3a5b9c` matches.
- Compile time: **verified** on ledger_bin, 3 cold builds, 0.11 s vs 0.12 s base — no regression.

**Pre-existing:** none newly observed. (Review-1's `g_dict.py` not rerun; the del/comprehension refusals are named compile-time refusals, not defects.)

**Unverified:** full 20-pair `bce_census`, the wider suite, tally/ticket/tree_fold compile time, `g_dict`, and icount (no generated C differs, so runtime cannot change).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1602821, "input": 75820, "output": 6394, "reasoning": 24287, "cache.write": 0, "cache.read": 1496320}]
    tool time: bash 4.3 min, read 0.0 min
        177s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_bce 
         24s bash   cd /tmp/rprobes && for p in n_bytes_collide n_tuple bytes_positive n_augmul n_setattr n_del; do echo "===== $p
         17s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 600 python3 tools/compile_phases.py lab/compare/src/ledger_bin/m
         17s bash   cd /tmp/base && timeout 600 python3 /home/runner/work/ail-ci/ail-ci/tools/compile_phases.py lab/compare/src/le
          7s bash   cat > /tmp/rprobes/dump.sh <<'EOF' #!/bin/bash # dump.sh REPO SRC [SYNTAX] repo=$1; src=$2; syn=${3:-python}; 
          7s bash   cd /tmp/rprobes && cat > init_cond.py <<'EOF' class R:     def __init__(self, pos: int) -> None:         self.
          4s bash   cd /tmp/rprobes && cat > store_in_other_fn.py <<'EOF' class R:     def __init__(self, pos: int) -> None: self.
          2s bash   cd /tmp/rprobes && cat > plain.py <<'EOF' def f(xs: list[int]) -> int:     s = 0     for x in xs:         s +=

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-05T12:05:42Z
