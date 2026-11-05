# job job-pyproof1-11051358  started 2026-11-05T05:00:16Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed both review defects and committed as `585195a`.

- Crate rows now run `ail_cargo.py build`; 5 of 6 are typed and match CPython, `fnvhash/main.py` is correctly `wrong` (runtime int64 overflow).
- CPython runs for every row, so missing artifacts can no longer masquerade as refusals.
- Base provenance now names the ref actually used (`work`, since no `integ` ref exists) instead of mislabelling `HEAD`.
- Census: **typed 29 / 55, general 16, refused 8, wrong 2**, geomean 6.59x. Both wrong rows have reproducers.

Verification: full census, all 7 reproducers via `cmp.sh`, `test_ail_examples_crate.py`, `test_ail_pyproof_report` (5 tests), `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` all pass; `update_manifest.py --check` rc 0.
[cost $0.0000, opencode tokens {"total": 5269343, "input": 111679, "output": 18317, "reasoning": 18707, "cache.write": 0, "cache.read": 5120640}]
    tool time: bash 32.6 min, edit 0.0 min, write 0.0 min
        633s bash   python3 lab/pyproof/report.py -j 2 > /tmp/pyproof-full.log 2>&1; echo rc=$?; tail -40 /tmp/pyproof-full.log
        632s bash   python3 lab/pyproof/report.py -j 2 > /tmp/pyproof-full2.log 2>&1; echo rc=$?; tail -25 /tmp/pyproof-full2.log
        324s bash   python3 tools/par_check.py -j 2 test_ail_pyproof_report test_ail_safetynet test_ail_files test_ail_corpus_find
        221s bash   rm -rf /tmp/pyproof-ref && python3 lab/pyproof/report.py --out /tmp/pyproof-ref --only examples/ffi/bindgen/me
         61s bash   rm -rf /tmp/pyproof-ref && python3 lab/pyproof/report.py --out /tmp/pyproof-ref --only examples/hybrid/fallbac
         12s bash   for f in lab/pyproof/repro/*.py; do echo "===== $f"; bash ~/tools/cmp.sh "$f" "$PWD"; done 2>&1 | grep -E '^==
         11s bash   bash ~/tools/cmp.sh /tmp/probes/int_overflow2.py $PWD; echo =====; bash ~/tools/cmp.sh /tmp/probes/int_overflo
         10s bash   cat > /tmp/crateprobe/run.sh <<'EOF' #!/bin/bash c=$1; file=$2; flags=$3; check=$4 d=/tmp/crateprobe/$c cd $d 

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change really does (one line):** It edits only the `lab/pyproof` census harness and its data/tests — builds the Rust crates with `ail_cargo.py build`, runs CPython before classifying every row (so a missing artifact cannot look like a refusal), compares full exit status, records the real base ref, and adds two `wrong` reproducers. No compiler or runtime file is touched.

**Claims checked**

| claim | verdict |
|---|---|
| crate rows built; 5 of 6 typed + `fnvhash/main.py` `wrong` | verified — independent `report.py --only examples/crate/*` gave typed 6, wrong 1 (fnvhash) |
| CPython runs for every row; no artifact-as-refusal | verified — all 55 records have `exit_cpython`; all 8 refused rows have `exit_cpython=0` |
| base provenance names `work`, not `HEAD`-as-`integ` | verified — `RESULTS.md`: `Base: work 88e666c…`; matches `git rev-parse work` |
| typed 29 / 55, general 16, refused 8, wrong 2, geomean 6.59x | verified — full re-run (634 s) produced zero per-row result diffs; 45 built rows geomean 6.589x |
| both wrong rows have reproducers | verified — `cmp.sh`: CPython exit 0 vs AIL exit 1 for `integer overflow in +` and `int()` |
| 7 reproducers behave as the README table says | verified — 5 bucket repros strict-refuse (rc 2/3); the 3 fallback repros build general/default and match stdout; 2 wrong repros overflow |
| `test_ail_pyproof_report`, `test_ail_safetynet`, `test_ail_examples_crate`, manifest check | verified — par_check `-j 2` both ok; crate 3 tests OK; `update_manifest.py --check` rc 0 |

Probes: a program exiting 3 on both sides is now `typed` (new full exit-status comparison), and a sibling-import fixture is `typed`; both match CPython. No compiler/runtime change, so there is no "unused feature C output" probe to run.

**Defects:** none.

**Pre-existing:** none.

**Unverified:** `test_ail_files` and `test_ail_corpus_findings3` (worker claims pass; not rerun, per instruction); speed impact (no hot code touched, so `icount` not applicable).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1499037, "input": 62999, "output": 6053, "reasoning": 18017, "cache.write": 0, "cache.read": 1411968}]
    tool time: bash 16.1 min
        635s bash   date; cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/pyproof-rerun && timeout 800 python3 lab/pyproof/repor
        178s bash   date; cd AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_pyproof_report test_ail_safety
        123s bash   date; cd /home/runner/work/ail-ci/ail-ci && for i in 1 2; do rm -rf /tmp/pyproof-measure$i; timeout 300 python
         12s bash   cd /home/runner/work/ail-ci/ail-ci && for f in lab/pyproof/repro/*.py; do echo "########## $f"; timeout 120 ba
          9s bash   date; cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/pyproof-crate && timeout 750 python3 lab/pyproof/repor
          5s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 600 python3 test_ail_examples_crate.py 2>&1 | tail -
          2s bash   cd /tmp && rm -rf strictprobe2 && mkdir strictprobe2 && cd strictprobe2 && i=0; for f in /home/runner/work/ail
          2s bash   cd /home/runner/work/ail-ci/ail-ci && for f in /tmp/rprobes/exit3.py /tmp/rprobes/sibling.py; do echo "### $f"

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-05T07:12:37Z
