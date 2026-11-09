# job job-wedge3d-11091228  started 2026-11-09T03:31:17Z  worker=chain reviewer=chain (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done. Committed under `lab/wedge3/wedge3d/` only (`5f8457c` + report follow-up `7c64acb8`). Hybrid tree: `job-obs5-op1109` at `69e2dcd0`.

- **dateutil**: hybrid **0/61** definitions native (plain and observed). CPython 1.117s, PyPy 1.078s, hybrid 1.130s, hybrid+obs 1.128s, ciso8601 0.149s → hybrid/CPython **1.011x**, hybrid/PyPy **1.047x**, hybrid/native **7.577x**.
- **ahocorapy**: hybrid **0/20** native (plain and observed). CPython 1.237s, PyPy 0.367s, hybrid 1.247s, hybrid+obs 1.223s, ahocorasick_rs 0.149s → hybrid/CPython **1.008x**, hybrid/PyPy **3.394x**, hybrid/native **8.355x**.
- Observed kinds changed no selection; every workload run was byte-identical to CPython.
- Top refusals: dateutil classes with bases/decorators (2.28s profiled self time); ahocorapy `self._zero_state` non-scalar field (2.70s).
- Probes `/tmp/probes/w3d_date_edges.py`, `w3d_aho_edges.py` match CPython/hybrid/observed/PyPy/native; `icount` unavailable (`perf_event_open` denied).
- Required checks passed: safetynet 5, files 18+1 skip, corpus findings3 2. No push.
[cost $0.0000, opencode tokens {"total": 5467749, "input": 129520, "output": 24567, "reasoning": 25470, "cache.write": 0, "cache.read": 5288192}]
    tool time: bash 8.1 min
        136s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 2500000; python3 AIL_CURRENT/test_ail_corpus_findings3.py > /t
         76s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 2500000; python3 AIL_CURRENT/test_ail_safetynet.py > /tmp/t_sa
         63s bash   ulimit -v 2500000; python3 lab/wedge3/wedge3d/harness.py -o lab/wedge3/wedge3d/results.json 2>&1 | tee /tmp/w3
         63s bash   ulimit -v 2500000; python3 lab/wedge3/wedge3d/harness.py -o lab/wedge3/wedge3d/results.json 2>&1 | tee /tmp/w3
         62s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 2500000; python3 AIL_CURRENT/test_ail_files.py > /tmp/t_files.
         23s bash   find /opt/hostedtoolcache -maxdepth 3 -iname '*pypy*' 2>/dev/null | head; find /opt/hostedtoolcache -maxdepth 
          9s bash   PP=/opt/hostedtoolcache/PyPy/3.10.16/x64/bin/pypy3; $PP --version | head -2; $PP -m ensurepip --default-pip >/
          6s bash   timeout 120 git fetch origin job-obs5-op1109 2>&1 | tail -20; echo RC=$?

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: wedge3d (lab measurement job)

**What the change really does:** adds only `lab/wedge3/wedge3d/**` (harness, two workload drivers, pinned requirements, `results.json`, `RESULTS.md`, `DEVLOG.md`). It builds the `job-obs5-op1109` hybrid (commit `69e2dcd0`, verified) on dateutil and ahocorapy, times CPython/PyPy/hybrid/hybrid+obs/ciso8601/ahocorasick_rs, and reports refusals. No compiler, runtime, or test module changed.

**Verified**
- `0` accelerated in all four builds (`build.json` `accelerated: []`); independently rebuilt both hot modules myself: 0 accelerated, 56/17 rejected.
- Times and ratios in `RESULTS.md` match `results.json` and are arithmetically correct; `native` rows are 7.58x / 8.36x. Conclusion (hybrid = CPython speed) holds.
- `icount` truly unavailable: `perf_event_open: Permission denied` (`perf_event_paranoid=4`).
- Worker probes reproduce: CPython/PyPy/native outputs identical for both edge-case probes.
- `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` all pass (`par_check -j 2`, 190 s).
- Only `lab/wedge3/wedge3d/**` changed; no pre-existing differences apply.

**Defects**
1. **Wrong function totals / headline.** `harness.py:264-268` and `296-299` count the hot module *after* `install_hybrid` has overwritten it with the generated `*_run.py`, so the AIL preamble's 3 helper defs are counted as library functions. Expected (actual library files): dateutil `_parser.py` **58 defs / 2 top-level / 54 methods**; ahocorapy `keywordtree.py` **17 / 0 / 17**. Actual reported: **61 / 4 / 54** and **20 / 2 / 17**, so "0/61" and "0/20" should be **0/58** and **0/17**. Probe: AST-count `.../dateutil/parser/_parser.py` and `.../ahocorapy/keywordtree.py`, or diff `build_plain/_parser.orig.py` (58 defs) against `_parser_run.py` (61).
2. **Refusal ranking polluted by stdlib `re`.** `harness.py:187` matches only `Path(fn).name`, and dateutil's hot basename `_parser.py` also matches `/usr/lib/python3.12/re/_parser.py`. Expected: only dateutil functions. Actual: 26 `re._parser` functions (0.00036 s) enter the profile; the "no refusal recorded" row lists `match`, `seek`, `tell`, `groups`, `_parse_sub`, and `RESULTS.md` cites `_escape`/`_parse_flags` as dateutil refusals. `hot_self_s` 2.447 s includes 0.00036 s of `re` time (dateutil-only 2.446855 s). Ranking order is unaffected, the table contents are not.
3. **Truncated refusal reason in `results.json`.** `normalise_reason` (`harness.py:172-177`) strips both `, stays in CPython` and ` stays in CPython` from `"method: calls a method that stays in CPython, stays in CPython"`. Expected `"method: calls a method that stays in CPython"`; actual `"method: calls a method that"` (`results.json:486`). `RESULTS.md` shows the full phrase, so the committed data and report disagree.

**Unverified:** exact per-module test counts (`5`, `18+1`, `2`) — modules passed but counts were not printed; wall times were not re-timed, only the saved artifacts inspected.

**Note (non-blocking):** the DEVLOG entry is in `lab/wedge3/wedge3d/DEVLOG.md`, not the root `DEVLOG.md`; defensible given "commit only `lab/wedge3/wedge3d/**`".

VERDICT: FIX
[cost $0.0000, opencode tokens {"total": 2936778, "input": 94120, "output": 9250, "reasoning": 36096, "cache.write": 0, "cache.read": 2797312}]
    tool time: bash 3.3 min
        191s bash   cd /home/runner/work/ail-ci/ail-ci && date && timeout 360 python3 tools/par_check.py -j 2 test_ail_safetynet t
          3s bash   cd /tmp/rprobes && rm -rf dtroot ahoroot dtbuild ahobuild *.log && mkdir -p dtroot ahoroot && /tmp/w3d-venv/bi
          0s bash   date; mkdir -p /tmp/rprobes && cd /tmp/rprobes && rm -rf dt aho && /tmp/w3d-venv/bin/python - <<'EOF' import s
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git log --oneline --all -- 'lab/**/DEVLOG.md' | head; echo ---; git log 
          0s bash   cd /tmp/probes && date && /tmp/w3d-venv/bin/python w3d_date_edges.py > /tmp/rprobes/d_py.out 2>&1; W3D_IMPL=na
          0s bash   /tmp/w3d-venv/bin/pip show ahocorasick_rs ahocorapy 2>/dev/null | grep -E "Name|Version"; echo ---; /opt/hoste
          0s bash   cd /home/runner/work/ail-ci/ail-ci && head -60 AIL_CURRENT/ailc.py; echo ---; grep -rn "ailc ext\|ailc.py ext\
          0s bash   for d in /tmp/w3d-ywjlm1nu/*/; do for b in $d/build_plain $d/build_obs; do [ -f $b/build.json ] && printf "%s 

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed all three review defects in `lab/wedge3/wedge3d/` and committed as `923d9c90`.

- Counts now come from the original hot modules: dateutil **58 / 2 / 54**, ahocorapy **17 / 0 / 17**.
- Refusal profiling matches the exact resolved path, so stdlib `re._parser` no longer pollutes dateutil (`hot_self_s` 2.473, dateutil-only).
- `normalise_reason` strips one suffix; `results.json` now stores `"method: calls a method that stays in CPython"`.
- Regenerated `results.json`/`RESULTS.md`; probes match across CPython, PyPy, native, hybrid, hybrid+obs.
- Required tests pass on the final commit: `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` (3 modules, 0 failed).
[cost $0.0000, opencode tokens {"total": 1350687, "input": 39569, "output": 8107, "reasoning": 6627, "cache.write": 0, "cache.read": 1296384}]
    tool time: bash 3.3 min, edit 0.0 min, read 0.0 min
        137s bash   cd /home/runner/work/ail-ci/ail-ci && date && timeout 900 python3 tools/par_check.py -j 2 test_ail_safetynet t
         62s bash   cd /home/runner/work/ail-ci/ail-ci && bash -c 'ulimit -v 2500000; /tmp/w3d-venv/bin/python lab/wedge3/wedge3d/
          0s bash   cd /tmp/probes && W=/tmp/w3d-bvb5q13w && PY=/tmp/w3d-venv/bin/python && PYPY=/opt/hostedtoolcache/PyPy/3.10.16
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --help 2>&1 | head -30; git status --sh
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check; echo exit=$?
          0s bash   pwd && git status && git log --oneline -5
          0s bash   cd /home/runner/work/ail-ci/ail-ci && /tmp/w3d-venv/bin/python - <<'EOF' import json, importlib.util, subproce
          0s bash   python3 -c 'import dateutil, ahocorapy; print(dateutil.__version__, ahocorapy.__version__)' 2>&1 | head -3; ls

## review 1
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
I have enough evidence. Writing the report.

**What the change really does.** It adds only `lab/wedge3/wedge3d/**` (harness, two workload drivers, pinned requirements, `results.json`, `RESULTS.md`, `DEVLOG.md`); no AIL compiler, runtime, or test file changes. It measures the `job-obs5-op1109` hybrid at commit `69e2dcd0` on python-dateutil and ahocorapy against CPython, PyPy, and native rewrites (ciso8601, ahocorasick_rs), and ranks the hybrid's refusal reasons.

**Verified (ran/reproduced myself)**
- `git diff work..HEAD` is only `lab/wedge3/wedge3d/**`; `AIL_CURRENT`, `tools`, `bench` untouched, so no base comparison applies.
- Rebuilt both hot modules at `69e2dcd0`: `accelerated: []`, rejected 56 and 17 — reproduces the "0 accelerated" headline. A trivial typed module does accelerate (`add`), so the build path is not broken.
- Counts: independently AST-counted installed modules -> dateutil `58 / 2 / 54`, ahocorapy `17 / 0 / 17`.
- `normalise_reason` now yields `"method: calls a method that stays in CPython"`; refusals.reasons in `results.json` contains it. `refusal_ranking` on a fresh cProfile run gives `hot_self_s` 2.451/2.687 (dateutil/aho), same rows as committed 2.473/2.680, and no `re/_parser` entries; the excluded `re` total is 0.000355 s, matching the DEVLOG's 0.00036.
- Full-size workload outputs are byte-identical to CPython for both libraries (50,000 dates; 100,000 repeats, 19,205,994-byte text, 500 matches). Saved edge-probe outputs are md5-identical across CPython/PyPy/native/hybrid/obs.
- Observed path end-to-end on ahocorapy: annotate keeps 17 defs, annotated run output equals CPython, rebuild gives 0 accelerated.
- `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: `par_check -j 2` -> 3 modules, 0 failed; worker logs confirm 5 / 18+1 skip / 2.
- `perf_event_open` really is denied (`paranoid=4`), so the missing icount column is legitimate.
- Report/`results.json` times and ratios are arithmetically consistent; medians are the median of the five listed runs.
- `update_manifest.py --check` exits 0.

**Defect**
1. `RESULTS.md` §1 says the 50,000-string date workload includes "±14:00 offsets". The generator `workloads/date_parse.py:make_strings` uses `off = (i*37) % 1440 - 720`, so offsets are only `-11:57 .. +11:56`; ±14:00 appears solely in `/tmp/probes/w3d_date_edges.py`. Probe `/tmp/rprobes/w3d_offsets.py` output: `offset strings=12500 min=-11:57 max=+11:56`, `has +14:00: False  has -14:00: False`. Expected per the report: ±14:00 offsets in the workload; actual: none. One-line report fix; no measured number or conclusion changes.

**Pre-existing.** None applicable — no AIL source is modified and the lab directory is new.

**Unverified.** I did not re-run the five-repetition wall timings (I verified the stored times are medians and reproduced outputs/builds/refusals); the dateutil annotate step was not re-run (only aho).

VERDICT: FIX
1. Fix the false workload-coverage sentence in `RESULTS.md` §1: state the actual offset range (`-11:57 .. +11:56`, or "up to ±12:00"), or extend `make_strings` to reach ±14:00. Probe `/tmp/rprobes/w3d_offsets.py` expected ±14:00 present, actual `min=-11:57 max=+11:56`, no ±14:00.
[commandcode stop=end_turn turns=42 out_tokens=67003]

FINAL VERDICT: FIX  2026-11-09T04:20:14Z
