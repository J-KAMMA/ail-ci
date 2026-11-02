# job job-rbprog23-11022330  started 2026-11-02T14:30:38Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Re-applied prog23 and committed as `a98c70d` on `job-rbprog23-11022330`.

- Conflict in `_promote_floats` resolved keeping both: existing `nsum_names` NSUM settling and incoming str/bytes/unannotated-set fixed points.
- Registered `test_ail_prog23` via `tests.d/test_ail_prog23.txt`; manifest regenerated and `--check` passes.
- `tools/diff_ids.py` does not exist in this tree or the fetched job, so only `update_manifest.py` ran.
- Probes in `/tmp/probes/prog23_*.py` (5 files: tuple/list bindings, conditional lists, int set ops, str/bytes set ops, set rebinds/aliases) all matched CPython on both general and default builds.
- Final-commit tests: `test_ail_prog23`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4/4 passed, 0 failed.
- Worktree clean except pre-existing untracked `.agent/pipeline.md`; nothing pushed.
[cost $0.0000, opencode tokens {"total": 1275450, "input": 94656, "output": 5866, "reasoning": 2704, "cache.write": 0, "cache.read": 1172224}]
    tool time: bash 13.0 min
        413s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_prog23 test_ail_safetynet test_
        312s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check && python3 tools/par_check.py -
         39s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/prog23_*.py; do echo "=== $(basename $p)"; bash ~/t
          8s bash   git fetch https://github.com/J-KAMMA/ail-ci.git job-prog23-11021945 && git rev-parse FETCH_HEAD
          4s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' from pathlib import Path p=Path('/tmp/probes/prog23_ife
          1s bash   cd /home/runner/work/ail-ci/ail-ci && git add AIL_CURRENT/python/pkg-v12/iterlower.py AIL_CURRENT/python/pkg-v
          1s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/python/pkg
          0s bash   git status && git log --oneline -5 && ls

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change does:** Re-applies the accepted prog23 typed-reach change: tuple/list target bindings in `known_sequences`, conditional numeric lists in `_numeric_field_kind`, unannotated int-set operators through `_set_value`, and str/bytes-set exclusions. Added code is line-for-line identical to the fetched accepted job except one blank line; the `_promote_floats` conflict keeps both the existing NSUM block and the incoming fixed points.

**Claims checked**
- Re-applied as `a98c70d`: verified.
- `_promote_floats` conflict keeps both sides: verified (added lines match original; NSUM code intact).
- `tests.d/test_ail_prog23.txt` registered, manifest regenerated, `--check` passes: verified.
- `tools/diff_ids.py` absent from tree and fetched job: verified.
- Worker's 5 `/tmp/probes/prog23_*` probes match CPython on both builds: verified by rerun.
- Final tests 4/4: `test_ail_prog23` (43.4s) and `test_ail_safetynet` (168.3s) rerun ok; `test_ail_files`, `test_ail_corpus_findings3` not rerun (reviewer scope) — unverified.
- Clean worktree except `.agent/pipeline.md`: verified.

**Probes** (~35, `/tmp/rprobes`, `cmp.sh` both builds): tuple/list bindings incl. mismatch, star, nested, chained, swap, aliases; conditional int/float/str lists, mixed/tuple branches; int/str/bytes/mixed/bool/float sets; empty/negative; aliases; mutation of operands/result; set values via args, list items, attributes, dict values, calls, keys, tuples; augmented ops; same-set ops; mutation during iteration; NSUM+sets. All matched CPython except the float-set case below, which is identical on base.

**C unchanged:** all 10 `lab/compare/src/*/main.ail` `program.c` byte-identical to base, plus `g02_026`, `g18_030`, `t102`, `t069`. `t115`/`t143` C changed (feature active).

**Pre-existing:** `set([1.5,2.5]) & set(...)` prints ints (`[2, 3]`) instead of floats (`[2.5, 3.5]`), also when aliased; base shows the identical DIFF, so not caused by this change.

**Unverified:** `test_ail_files`/`test_ail_corpus_findings3` (not rerun per reviewer scope); no instruction-count/speed comparison (change is compile-time).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1663584, "input": 93166, "output": 11320, "reasoning": 12730, "cache.write": 0, "cache.read": 1546368}]
    tool time: bash 9.3 min
        169s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 900 python3 ../tools/par_check.py -j 2 test_
        104s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/cmpC_head /tmp/cmpC_base && mkdir -p /tmp/cmpC_head /tmp/cmp
         55s bash   cd /tmp/rprobes && for p in *.py; do echo "######## $p"; timeout 300 bash ~/tools/cmp.sh /tmp/rprobes/$p /home
         38s bash   cd /tmp/probes && for p in prog23_*.py; do echo "######## $p"; timeout 300 bash ~/tools/cmp.sh /tmp/probes/$p 
         35s bash   cd /tmp/rprobes && for p in set_str_sources.py set_int_sources.py set_cond_source.py set_bytes_sources.py set_
         20s bash   cd /tmp/rprobes && for p in cond_float_append.py set_alias_plain.py list_alias_plain.py set_op_alias_operand.p
         19s bash   cd /tmp/rprobes && cat > set_floats_alias.py <<'EOF' def run() -> None:     a = set([1.5, 2.5])     b = a     
         18s bash   cd /tmp/rprobes && cat > set_floats.py <<'EOF' def run() -> None:     a = set([1.5, 2.5, 3.5])     b = set([2.

## full suite
test_ail_libc_names

## worker report (suite fix)
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed `b50a293`.

Root cause: the new `untyped_str_sets` / `untyped_byte_sets` Ctx fields were plain aliased sets, so `_qc_setattr` marked the context uncacheable and disabled the query memo cache. That made compilation of many-function programs take minutes.

Fix: added both fields to `_QC_ALIASED_OK` (same treatment as `slist_names`) and refreshed the manifest pin.

Verified:
- `test_ail_libc_names`: 5 tests OK
- `test_ail_prog23`: 7 tests OK
- `test_ail_manifest_compiler`: OK
- `tools/update_manifest.py --check`: OK
[cost $0.0000, opencode tokens {"total": 3270114, "input": 112735, "output": 10588, "reasoning": 9383, "cache.write": 0, "cache.read": 3137408}]
    tool time: bash 25.1 min, edit 0.0 min, read 0.0 min
        300s bash   cd AIL_CURRENT && python3 - <<'PY' import subprocess, sys, os, time, re text=open('/tmp/combined.ail').read() 
        188s bash   cd AIL_CURRENT && python3 - <<'PY' import subprocess, sys, os, time, re, signal text=open('/tmp/combined.ail')
        180s bash   cd AIL_CURRENT && timeout 280 python3 -m unittest -v test_ail_libc_names.LibcNameTests.test_libc_named_functio
        120s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_libc_names 2>&1 | tail -100
        120s bash   pkill -9 -f 'python/pkg-v12/pyc.py' || true; sleep 1; pgrep -af pyc.py || true
        120s bash   pkill -9 -f 'pyc[.]py' || true; sleep 1; wc -c /tmp/pyc.err /tmp/pyc.out; cat /tmp/pyc.err | tail -50; sed -n 
        120s bash   cd AIL_CURRENT && time timeout 120 env AIL_FE_JOBS=1 python3 -X utf8 python/pkg-v12/pyc.py --file /tmp/combine
         60s bash   cp /tmp/ailc-xlk1h330/combined.ail /tmp/combined.ail; kill $(cat /tmp/pid) 2>/dev/null; pkill -f 'pyc.py --fil

## full suite again
no new failures

FINAL VERDICT: ACCEPT  2026-11-02T17:59:19Z
