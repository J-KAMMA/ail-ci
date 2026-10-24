# job job-rbfuzz54-10240915  started 2026-10-24T00:15:40Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Applied fuzz54 on top of `job-rbfuzz54` and committed as `317043d`.

- Merged `seq_type`: non-numeric mixed displays refuse; rbfuzz54 numeric fallback retained; `int`/`bool` widen to `int`.
- Added/registered `test_ail_fuzz54` in `ail_check.py` and `ci_shards.json`; added DEVLOG entry.
- `update_manifest.py` ran; `--check` exits 0.
- Probes (all 9 same stdout on both builds vs CPython): `p01_mixed_list_repr`, `p02_mixed_nested`, `p03_numeric_mixes`, `p04_mixed_via_arg`, `p05_mixed_via_item`, `p06_mixed_via_attr`, `p07_mixed_via_dictvalue`, `p08_homogeneous_nested`, `p09_boundary_empty_none`.
- Tests on final commit: `test_ail_fuzz54`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4/4 passed, 0 failed (203s).
- `tools/diff_ids.py` is absent from this snapshot (`No such file or directory`); no DIFFERENCES rows were added.
- Note: an exploratory outer list of mixed displays crashed in `nested_lists.row_class` identically on the base commit, so it is pre-existing and was not caused by this change.
[cost $0.0000, opencode tokens {"total": 1627092, "input": 52661, "output": 7206, "reasoning": 7801, "cache.write": 0, "cache.read": 1559424}]
    tool time: bash 8.5 min, edit 0.0 min
        261s bash   python3 tools/par_check.py -j 2 test_ail_fuzz54 test_ail_safetynet test_ail_files test_ail_corpus_findings3 2>
        204s bash   git show --stat --oneline HEAD | head -12; python3 tools/par_check.py -j 2 test_ail_fuzz54 test_ail_safetynet 
         30s bash   for p in /tmp/probes/*.py; do echo "===== $(basename "$p")"; bash ~/tools/cmp.sh "$p" "$PWD"; done > /tmp/prob
          5s bash   git worktree add --detach /tmp/base HEAD >/dev/null 2>&1; bash ~/tools/cmp.sh /tmp/probes/p05_mixed_via_item.p
          4s bash   cat > /tmp/probes/p05_mixed_via_item.py <<'EOF' def main() -> None:     xs = [{"k": [["a"], {"x": "y"}]}, {"k"
          1s bash   git fetch https://github.com/J-KAMMA/ail-ci.git job-fuzz54-10231352 2>&1 | tail -5
          1s bash   git remote -v; git fetch https://github.com/J-KAMMA/ail-ci.git integ 2>&1 | tail -3; git ls-tree -r FETCH_HEAD
          0s bash   git ls-tree -r FETCH_HEAD --name-only | grep -E 'diff|DEVLOG|DIFFER'; echo ---; git branch -a; git ls-remote h

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review report

**Change reviewed:** `317043d` — `Exprs.seq_type` in `AIL_CURRENT/python/pkg-v12/tupexpr.py` now refuses non-numeric mixed displays, retains the rbfuzz54 numeric fallback, and widens `bool`/`int` to `int`; adds/registers `test_ail_fuzz54`, DEVLOG, MANIFEST.

**Probes** (`/tmp/rprobes`, run with `cmp.sh` on HEAD and `/tmp/base`, both builds):

- Match CPython on both builds: `p01_repr_forcing`, `p02_via_arg`, `p03_via_container`, `p04_bool_int`, `p05_numeric`, `p06_empty_none`, `p08_homogeneous`, `p10_unrelated`, `p11_bool_expr`, `p12_mixed` (accepted test body), `p13_homog`, `p14_annot_bool_int`, `p15_annot_numeric`, `p16_bool_int_float`, `p17_annot_int_only`, `p18_hole_mixed`.
- Fail identically on HEAD and `/tmp/base` (pre-existing, not caused):
  - `p07_nested_mixed`: `TypeError` in `nested_lists.row_class` (str + tuple).
  - `p09_mutation`: `TypeError` in `pyfunc._fstring_field` (“not all arguments converted”).
- Worker’s 9 probes rerun on HEAD: all same stdout on both builds.

**Non-feature C unchanged:** `program.c` byte-identical base vs HEAD for `p10`, `p08`, and gdev `g00_000/g00_002/g00_004` via `--debug-dir`; no icount needed.

**Tests on HEAD:** `test_ail_fuzz54`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4/4 pass, 203 s.

**Report claims:** applied/commit verified; merge description verified; test registration and DEVLOG verified; `update_manifest.py --check` exits 0; `tools/diff_ids.py` confirmed absent; 9 probes verified; 4 tests verified; pre-existing crash confirmed.

**Notes:** On this tree the base already falls back generically for mixed displays, so the new refusal is not output-observable; no regression found. Full suite not run, per instructions.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1496600, "input": 41365, "output": 26268, "reasoning": 1639, "cache.write": 0, "cache.read": 1427328}]
    tool time: bash 6.6 min, write 0.0 min
        204s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_fuzz54 tes
         34s bash   date; cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/*.py; do echo "===== $(basename "$p")"; bash
         31s bash   date; cd /tmp/base && for p in /tmp/rprobes/p01_repr_forcing.py /tmp/rprobes/p02_via_arg.py /tmp/rprobes/p03_v
         30s bash   date; cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/*.py; do echo "===== $(basename "$p")"; bash 
         18s bash   cd /tmp/rd && rm -f q_head q_base; for p in p05_numeric p14_annot_bool_int p13_homog p01_repr_forcing; do cp /
         15s bash   cd /home/runner/work/ail-ci/ail-ci && python3 -c "import sys; sys.path.insert(0,'AIL_CURRENT'); import test_ai
         13s bash   date; for d in /home/runner/work/ail-ci/ail-ci /tmp/base; do echo "##### $d"; cd "$d"; for p in /tmp/rprobes/p
          9s bash   cd /tmp && rm -rf gd && mkdir gd && cd gd; for g in g00_000 g00_002 g00_004; do cp ~/corpus/gdev/$g.py $g.ail;

FINAL VERDICT: ACCEPT  2026-10-24T00:41:20Z
