# job job-rbprog28-11022135  started 2026-11-02T12:37:54Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Applied and committed as `36ba7a1`.

- Resolved pyfunc conflicts by keeping this branch's richer enumerate-pair support plus the accepted max/min key, set-literal and pre-binding fixes.
- `python3 tools/diff_ids.py` is not present anywhere in this repo (or its history), so it could not be run.
- `python3 tools/update_manifest.py` ran; `--check` passes.
- Tests on final tree:
  - `test_ail_prog28`: 6/6 OK
  - `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: 25 tests OK (1 skipped)
  - targeted `test_ail_prog5`, `test_ail_prog11`, `test_ail_int_dict_set`, `test_ail_sort_keys`: 26/26 OK
- Probes: 5/5 (`p1`–`p5`, dict min/max keys, enumerate listcomp, set literals, trim variants, str-set key) match CPython on both `cmp.sh` builds.

Nothing pushed.
[cost $0.0000, opencode tokens {"total": 2170130, "input": 65490, "output": 7610, "reasoning": 7942, "cache.write": 0, "cache.read": 2089088}]
    tool time: bash 12.7 min, edit 0.0 min
        600s bash   python3 -m unittest test_ail_safetynet test_ail_files test_ail_corpus_findings3 2>&1 | tail -30
        112s bash   python3 -m unittest test_ail_prog5 test_ail_prog11 test_ail_int_dict_set test_ail_sort_keys 2>&1 | tail -30
         21s bash   mkdir -p /tmp/probes/prog28 && cat > /tmp/probes/prog28/p1_maxmin_dict_key.py <<'PY' class Box:     def __init
         11s bash   python3 -m unittest test_ail_prog28 2>&1 | tail -5; cd /home/runner/work/_temp/w2 && python3 tools/update_mani
          9s bash   python3 -m unittest test_ail_prog28 -v 2>&1 | tail -40
          7s bash   git fetch https://github.com/J-KAMMA/ail-ci.git job-prog28-11021550 2>&1 | tail -5 && git diff d08d67fe7820c7e
          1s bash   git add AIL_CURRENT/python/pkg-v12/pyfunc.py AIL_CURRENT/test_ail_prog28.py AIL_CURRENT/tests.d/test_ail_prog2
          1s bash   sed -n '19760,19785p' AIL_CURRENT/python/pkg-v12/pyfunc.py; python3 -c "import ast; ast.parse(open('AIL_CURREN

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Change:** adds dict/set key-kind typing for `max/min(key=...)`, skips the synthesized iterlower holder subscript during pre-binding, and treats container literals as non-numeric; keeps the branch's existing richer enumerate-pair support. Adds the prog28 test, DEVLOG, DIFFERENCES rows and lab notes.

**Defect**
1. `DIFFERENCES.md` removes the `# DIFFERENCES` title and the `| id | area | difference | status |` / separator lines. The accepted commit adds only three rows below that table header. Expected: header unchanged, three rows added. Actual: `git diff work..HEAD -- DIFFERENCES.md` shows 4 deletions plus the 3 row additions, so the table is now headerless. No source probe applies; this is an extra, unrequested change.

**Checks**
- Own probes `/tmp/rprobes/p1`–`p7`: all match CPython on both `cmp.sh` builds; `p7` also passes `--strict`.
- Worker probes `/tmp/probes/prog28/p1`–`p5`: 5/5 match on both builds.
- `test_ail_prog28` and `test_ail_safetynet`: pass (`-j 2`).
- All ten `lab/compare` programs: generated C byte-identical to `/tmp/base`.
- `tools/update_manifest.py --check`: passes.
- `tools/diff_ids.py`: absent from the repo and history; report verified.
- Only `DIFFERENCES.md` ID prefix changes are otherwise expected (`C?-job-rbprog28-...`).

**Unverified:** instruction counts; `perf_event_open` is denied in this runner. Other targeted modules reported by the worker were not rerun, per review scope.

VERDICT: FIX
[cost $0.0000, opencode tokens {"total": 2199923, "input": 120117, "output": 8149, "reasoning": 11497, "cache.write": 0, "cache.read": 2060160}]
    tool time: bash 6.4 min
        212s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_prog28 test_ail_safetynet 2>&1 | tail -30; date
         57s bash   set -e for t in rail_transfer scar_life echo_pack tally_lang berth_sim ledger_bin term_rank; do   for side in 
         39s bash   set -e for t in chain_relax ticket_audit tree_fold; do   for side in head base; do     wt=$PWD; [ $side = base
         34s bash   for f in /tmp/rprobes/*.py; do echo "===== $f"; bash ~/tools/cmp.sh "$f" "$PWD" 2>&1 | tail -12; done; date
         21s bash   for f in /tmp/probes/prog28/*.py; do echo "===== $(basename $f)"; bash ~/tools/cmp.sh "$f" "$PWD" 2>&1 | tail 
         10s bash   set -u for f in /tmp/rprobes/*.py; do   d=$(mktemp -d /tmp/rsXXXXXX); cp "$f" "$d/p.ail"   ( cd "$d" && python
          4s bash   cc -O2 -w -include signal.h -include stdlib.h -o /tmp/icount tools/icount.c && echo built for side in head bas
          3s bash   d=$(mktemp -d /tmp/dbgXXXXXX); AIL_NO_CACHE=1 AIL_SERVER=0 python3 AIL_CURRENT/ail_chatgpt.py compile lab/comp

## worker report 1
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Fixed and committed as `acf8e49`.

- `DIFFERENCES.md`: restored the `# DIFFERENCES` title and table header; diff vs `8da1f54` is now exactly 3 row insertions, 0 deletions.
- Probes (both `cmp.sh` builds, all match CPython): `prog28/p1`–`p5`, plus new `rb2/p6` (str list/dict keys through args, list items, attributes, dict values, empty/default) and `rb2/p7` (list/tuple/set/dict literals from names). 7/7.
- Tests on final commit (`-j 2`): `test_ail_prog28`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed.
- `tools/update_manifest.py` and `--check` pass; `tools/diff_ids.py` does not exist in the repo.
- Nothing pushed; only `DIFFERENCES.md` committed (`.agent/pipeline.md` left untracked).
[cost $0.0159, opencode tokens {"total": 386387, "input": 81631, "output": 2470, "reasoning": 2126, "cache.write": 0, "cache.read": 300160}]
    tool time: bash 13.7 min
        416s bash   git diff 8da1f54 --stat -- DIFFERENCES.md; git diff 8da1f54 -- DIFFERENCES.md | grep -c '^[+-][^+-]' ; cd AIL_
        374s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_prog28 test_ail_safetynet test_ail_files test_ai
         29s bash   for f in /tmp/probes/prog28/*.py /tmp/probes/rb2/*.py; do echo "===== $f"; bash ~/tools/cmp.sh "$f" "$PWD" 2>&
          1s bash   python3 tools/update_manifest.py && python3 tools/update_manifest.py --check; echo "manifest rc=$?"; python3 t
          0s bash   python3 tools/update_manifest.py --check; echo "rc=$?"; git status --short
          0s bash   git add DIFFERENCES.md && git diff --cached --stat && git commit -m "$(cat <<'EOF' job rbprog28: restore DIFFE
          0s bash   pwd && git status && git log --oneline -8 && git branch --show-current
          0s bash   ls -l ~/tools/cmp.sh 2>/dev/null; git show --stat HEAD; echo "---DEVLOG top---"; sed -n '1,12p' DEVLOG.md; ech

## review 1
[model opencode-go/deepseek-v4.1-flash]
**Review report — `prog28` re-apply (HEAD `acf8e49`, 2 commits over `work`/`8da1f54`)**

**What the change really does:** It re-applies the accepted `job-prog28` change: `_etype`/`_is_str_expr` now give `min`/`max(..., key=)` over a typed map/list container the container's key/element kind; container literals are excluded from `_numeric_expression_needed`; a subscript of an iterlower-synthesized name is left to float pre-binding. Adds `test_ail_prog28`, `tests.d` entry, `lab/progfix/prog28.md`, DEVLOG, 3 DIFFERENCES rows, manifest shards. The accepted enumerate-pair hunks are absent, but the base already contains a more general pair-listcomp implementation (`_listcomp_pair_into_temp` + `_pair_plan`), so dropping them keeps the fix and the accepted test still passes.

**Claims checked**
- DIFFERENCES vs `8da1f54` = 3 row insertions, 0 deletions; title/header intact — verified.
- 7/7 worker probes match CPython on both builds — verified (reran).
- 4 modules (`test_ail_prog28`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`) pass on HEAD — verified, 0 failed, 275 s.
- `update_manifest.py --check` passes; `tools/diff_ids.py` is absent — verified.
- "only DIFFERENCES.md committed" — true only for `acf8e49`; the whole job also contains `36ba7a1` (pyfunc/test/docs), which the report does not describe. Not a defect.
- Unpushed (`ahead 2`), only `.agent/pipeline.md` untracked — verified.

**Probes I added** (`/tmp/rprobes/`): key kinds via argument/attribute/list item/dict value, bytes keys, `d.keys()`/`items()`, str/float/int/set sources, defaults, ties, side-effecting key; dict views; container literals from names incl. aliasing/mutation/comprehensions; enumerate/zip/items pairs incl. slicing and mutation during iteration; shadowed builtin and raising key. All matched CPython on both `cmp.sh` builds; unsupported strict shapes were named refusals.

**Unchanged-C spot checks:** compare-lab `berth_sim/echo_pack/ledger_bin/term_rank/ticket_audit` produce identical binary sha; the other five refuse identically. `g00_000`, `g04_012`, `g22_020`, `t441` identical sha; `g01_002`, `t489` identical refusal logs. No pre-existing differences found.

**Unverified:** instruction counts — `perf_event_open` denied and no valgrind. (Typed `g07_036` binary shrank 97 KB → 30 KB and matches CPython output.)

**VERDICT: ACCEPT**
[cost $0.0645, opencode tokens {"total": 2506196, "input": 287221, "output": 9292, "reasoning": 15379, "cache.write": 0, "cache.read": 2194304}]
    tool time: bash 11.8 min
        289s bash   cd /tmp/cdiff; ROOT=/home/runner/work/_temp/w2; printf '%s\n' $ROOT/lab/compare/src/*/main.py | while read t; 
        276s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_prog28 test_a
         40s bash   cd /home/runner/work/_temp/w2; for f in /tmp/probes/prog28/*.py /tmp/probes/rb2/*.py; do echo "===== $f"; bash
         39s bash   cd /home/runner/work/_temp/w2; for f in /tmp/rprobes/r*.py; do echo "===== $(basename $f)"; bash ~/tools/cmp.s
         37s bash   cd /tmp; rm -rf ctest; mkdir ctest; cd ctest; AIL_NO_CACHE=1 AIL_QUIET_FALLBACK=1 python3 /home/runner/work/_t
          7s bash   cat > /tmp/rprobes/r6_typed_struse.py <<'EOF' class Box:     def __init__(self, d: dict[str, int]) -> None:   
          6s bash   cd /tmp; rm -rf strictp; mkdir strictp; cd strictp; ROOT=/home/runner/work/_temp/w2; for f in /tmp/rprobes/r*.
          5s bash   cat > /tmp/rprobes/r5_minmax_misc.py <<'EOF' def mymax(xs: list[int]) -> int:     return -1   def use_shadow(x

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-02T14:55:55Z
