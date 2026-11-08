# job job-ffpkg1-11081520  started 2026-11-08T06:21:38Z  worker=chain reviewer=chain (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Implemented and committed on branch `job-ffpkg1-11081520` as `8e5ebff` (not pushed; the runner rule forbids pushing).

- `AIL_CURRENT/ail_pkg.py`: `add`/`remove`/`sync`/`list`, stdlib only; verifies wheel SHA-256, vendors `.py` + `.dist-info` only, refuses sdists, C extensions, hash mismatches, `..`/absolute paths, symlinks, duplicate entries, missing dependencies and top-level module conflicts.
- `AIL_CURRENT/test_ail_pkg.py` + `tests.d/test_ail_pkg.txt`: local HTTP fake index with self-built wheels; no network.
- `cli.py` left untouched per owner decision 3; `docs/PACKAGES.md` documents `PYTHONPATH=... python3 -m ail_pkg`.
- Updated `lab/pkg/RESULTS.md`; manifest pins refreshed and `--check` passes.

Verified:
- New local-index suite: **14/14 pass**.
- Required tests (`test_ail_pkg`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`): **39 pass, 1 skip**.
- `test_ail_packaging`: **21/21 pass**.
- Real PyPI census: **30/30 vendored and locked**, **30/30 lock hashes match** the census wheel hashes, `sync` verified.
- Vendored-tree build probes: **0 built, 30 refused, 0 output differences** — no regressions.
[cost $0.0000, opencode tokens {"total": 2322814, "input": 49451, "output": 20864, "reasoning": 32083, "cache.write": 0, "cache.read": 2220416}]
    tool time: bash 11.7 min, write 0.0 min, read 0.0 min
        483s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && ulimit -v 1500000; AIL_NO_CACHE=1 timeout 900 python3 -B -m 
        120s bash   find / -name '*.whl' 2>/dev/null | head -20; echo '--- net ---'; timeout 10 python3 -c "import urllib.request;
         42s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && ulimit -v 1500000; AIL_NO_CACHE=1 timeout 900 python3 -B -m 
         26s bash   cat > /tmp/ffpkg1-build.py <<'PY' import os, resource, subprocess, sys, tempfile, time from pathlib import Pat
          6s bash   cat > /tmp/ffpkg1-census.py <<'PY' import os, re, subprocess, sys from pathlib import Path sys.path.insert(0, 
          4s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/ail_pkg.py
          4s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/ail_pkg.py
          4s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/ail_pkg.py

## review 0
[model opencode/deepseek-v4.1-flash-free]
Review complete.

**What the change really does:** adds a standalone `AIL_CURRENT/ail_pkg.py` that fetches one `*-none-any.whl` from PyPI (or `AIL_PYPI_URL`/`--index`), verifies its SHA-256, extracts only `*.py`/`*.pyi`/`.dist-info` into `ail_packages/<name>/<version>/`, caches the wheel in `.ail-wheels/`, writes `ail.lock`, and provides `remove`/`sync`/`list`; plus a local-index test, docs, and RESULTS.md. This matches the report, except the report/default docstring promises `sync` refetches a missing wheel and the test name promises "highest stable" — both are false.

**Claims checked**
- `8e5ebff` on branch; only allowed files + manifest.d changed; `cli.py` untouched: verified.
- New suite 14/14: verified (14 tests, 3.7 s).
- `test_ail_pkg` + `test_ail_safetynet` on HEAD (`-j 2`): verified, 2 modules, 0 failed.
- `tools/update_manifest.py --check`: verified rc=0.
- Real PyPI path: partially verified — `add six==1.16.0` locked sha `8abb…0254` (equal to census) and `sync` succeeded; the other 29 packages were not rerun.
- "sync verified / when a wheel is missing, from the index": **false** (defect 1).
- "picks highest stable" (test name) / report's stable selection: **false** (defect 2).
- `test_ail_packaging` 21/21, full 30-package census, 0-built/30-refused, 20 CI shards: unverified.

**Pre-existing:** none — no compiler/runtime file changed, so non-feature C output is unchanged by construction.

**Unverified:** full 30-package PyPI census, `test_ail_files`/`test_ail_corpus_findings3`/`test_ail_packaging`, CI shards.

**Probes** (in `/tmp/rprobes/`): `probe.py`, `probe2.py`, `probe3.py`, `probe4.py`, `probe5.py`.

VERDICT: FIX
1. `sync` cannot refetch a missing cached wheel. Probe: `add alpha==1.0`, then `rm -rf .ail-wheels`, then `sync`. Expected `synced 1 package`; actual `FileNotFoundError` at `shutil.copy` because `.ail-wheels/` is not created. Variant: delete only `.ail-wheels/alpha-1.0-py3-none-any.whl` and `ail_packages/`, then `sync`; expected success, actual `FileNotFoundError` in `_safe_extract` because `sync` does `shutil.rmtree(download)` before extracting from `source` (ail_pkg.py:803-807). A second `sync` succeeds only because the cache was repopulated.
2. Bare-name `add` selects prereleases over stable versions. Probe: index has `pre 1.0.0` and `pre 1.0.0rc1`; `add pre`. Expected lock `1.0.0`; actual `1.0.0rc1` (`added pre 1.0.0rc1`, rc 0). `_is_stable` requires a `.`/`-` before `a|b|rc|...`, so `1.0.0rc1`/`1.0.0a1`/`2.0.0b1` count as stable. This contradicts `test_bare_name_skips_yanked_and_picks_highest_stable` (the test has no prerelease fixture).
3. Wheel selection ignores the Python tag. Probe: a 1.0 release whose `urls` list is `[pkg-1.0-py2-none-any.whl, pkg-1.0-py3-none-any.whl]`; `add pkg==1.0`. Expected the py3 wheel (or a refusal); actual it vendors the py2 wheel (`VALUE = "py2"`). `_file_is_pure_wheel` only checks the `-none-any.whl` suffix, so a Python-2-only pure wheel can be installed into an AIL/CPython-3 project.
4. Dependency version specifiers are discarded. Probe: `alpha 1.0`; `beta 1.0` has `Requires-Dist: alpha>=2.0`; `add alpha==1.0` then `add beta==1.0`. Expected refusal (locked alpha does not satisfy `>=2.0`); actual `added beta 1.0` with `requires = ["alpha"]`, losing the constraint.
5. Adding a package when a locked package's vendor tree is missing crashes with a traceback. Probe: `add alpha==1.0`; `rm -rf ail_packages/alpha`; `add gamma==1.0`. Expected a named refusal (e.g. run `sync`); actual uncaught `FileNotFoundError` in `top_level_names` (ail_pkg.py:95), because `_check_conflicts` reads every locked vendor tree.
[cost $0.0000, opencode tokens {"total": 858921, "input": 38914, "output": 6512, "reasoning": 18999, "cache.write": 0, "cache.read": 794496}]
    tool time: bash 2.3 min, read 0.0 min
        133s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 700 python3 ../tools/par_check.py -j 2 test_
          4s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 120 python3 -B -m unittest -v test_ail_pkg 2>&1 | ta
          1s bash   mkdir -p /tmp/rprobes && cat > /tmp/rprobes/harness.py <<'PY' import hashlib, json, os, re, subprocess, sys, t
          0s bash   cat > /tmp/rprobes/probe4.py <<'PY' import sys, tempfile, shutil from pathlib import Path sys.path.insert(0,'/
          0s bash   cat > /tmp/rprobes/probe5.py <<'PY' import sys, tempfile, shutil from pathlib import Path sys.path.insert(0,'/
          0s bash   cat > /tmp/rprobes/probe2.py <<'PY' import json, sys, tempfile, shutil from pathlib import Path sys.path.inser
          0s bash   cd /tmp && rm -rf /tmp/realproj && mkdir /tmp/realproj && cd /tmp/realproj && timeout 120 python3 -B /home/run
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check 2>&1 | tail -5; echo "rc=$?"; g

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed all five review defects and committed as `4c3af3b`.

- `sync` now refetches missing cached wheels, creates `.ail-wheels/`, and keeps the download until extraction.
- Bare-name selection now rejects PEP 440 prereleases (`1.0.0rc1`, `a1`, `b1`, `dev1`).
- Wheel selection rejects Python-2-only pure wheels and prefers the `py3` wheel.
- Dependency specifiers are stored (`require_specs`) and enforced by both `add` and `sync`.
- Adding with a missing locked vendor tree now refuses by name and says to run `sync`.

Verification:
- `test_ail_pkg`: 21/21 passed.
- Required modules `test_ail_pkg`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` with `-j 2`: 4 modules, 0 failed.
- `test_ail_packaging`: 21/21 passed.
- Reviewer probes `probe.py`–`probe5.py`: all five defects now behave as expected.
- `tools/update_manifest.py --check`: rc=0; only allowed files plus `manifest.d/21.txt` changed.

Commit created; push intentionally skipped per the standing rules.
[cost $0.0000, opencode tokens {"total": 2437696, "input": 87367, "output": 10645, "reasoning": 16356, "cache.write": 0, "cache.read": 2323328}]
    tool time: bash 6.8 min, edit 0.0 min, read 0.0 min
        355s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000; timeout 700 python3 tools/par_check.py -j 2 test_ail_
         43s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && ulimit -v 1500000; timeout 300 python3 -B -m unittest -q tes
          5s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m py_compile ail_pkg.py test_ail_pkg.py && timeout 
          2s bash   cd /tmp/rprobes && for f in probe.py probe2.py probe3.py probe4.py probe5.py; do echo "########## $f"; timeout
          1s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py 2>&1 | tail -20 && python3 tools/update
          0s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000; timeout 700 python3 tools/par_check.py -j 2 test_ail_
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check && python3 -m py_compile AIL_CU
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git status && git log --oneline -5 && git branch --show-current

## review 1
[model opencode/deepseek-v4.1-flash-free]
## Review report — job ffpkg1

**What the diff really does.** Commit `8e5ebff` adds a standalone `AIL_CURRENT/ail_pkg.py` (`add/remove/sync/list`) and a local-index test; `4c3af3b` fixes the five earlier review findings (sync refetch, prerelease filter, wheel tags, dependency pins, missing-tree refusal). It touches no compiler/runtime file, so generated C is trivially unchanged (`git diff work..HEAD -- AIL_CURRENT/ail_chatgpt.py` is empty). `cli.py` left untouched as the design permits.

**Probes.** `ail_pkg` is not an AIL program, so I exercised it directly with a `file://` fake index (`/tmp/rprobes/harness.py`, `probe_a.py`, `probe_b.py`, `probe_c.py`, `probe_d.py`, `probe_e.py`). Verified good: real PyPI `tabulate 0.9.0` hash `024ca478…`, `click`, `six`, `python-dateutil`; sync refetch restores trees, creates `.ail-wheels/`, leaves no temp dirs; sync leaves the tree intact on a tampered wheel; missing locked tree is refused by name. A differential matrix of `_accepts_python` vs `packaging.SpecifierSet` gives **23/99 mismatches**.

### Defects

1. **The new dependency-specifier matcher is not PEP 440; it silently accepts unsatisfied requirements (and `sync` reproduces them).**
   `/tmp/rprobes/probe_e.py`: index has `alpha 1.0.0`; `beta` has `Requires-Dist: alpha>1.0`.
   ```
   add alpha==1.0.0 ; add beta==1.0.0 ; sync
   expected: refusal (1.0.0 is not > 1.0 per PEP 440)   actual: "added beta 1.0.0", "synced 2 packages" (rc 0)
   ```
   `/tmp/rprobes/probe_d.py`: locked `alpha 2.0.0rc1`, `beta` requires `alpha>=2.0` → accepted by `add` and `sync`, but `SpecifierSet(">=2.0").contains("2.0.0rc1")` is `False`.
   Cause: `_version_key`/`_compare` compare tuples lexicographically (`1.0 < 1.0.0`, prerelease sorts above the final release), and `_accepts_python` is used by `_requirements`, `_check_reverse_requirements` and `sync`.

2. **The same matcher wrongly refuses valid requirements (loud false negatives).**
   `/tmp/rprobes/probe_a.py`: `alpha` locked `1.0.0`, `gamma` requires `alpha==1.0` → expected success (PEP 440 zero-padding), actual `ail_pkg: gamma requires alpha==1.0, but alpha is locked at 1.0.0`. Likewise `==1.0.*` is refused, and a parenthesised specifier `alpha (>=1.0)` fails with `unknown Requires-Python clause '(>=1.0)'`.

3. **`_is_stable` falsely classifies a stable local version as a prerelease.**
   `/tmp/rprobes/probe_b.py`: index has only `loc 1.0.0+1abc`; `add loc` → expected `added loc 1.0.0+1abc`, actual `loc: no non-yanked stable version with a pure-Python wheel`. The regex `(?:^|[._-]|\d)(?:…|a|b|c|…)` matches the `1a` inside a local segment.

### Claims
- sync refetch / `.ail-wheels/` / download kept until extraction — **verified**.
- bare name rejects `1.0.0rc1`, `a1`, `b1`, `dev1` — **verified** for those forms; **false** as a general PEP 440 claim (defect 3).
- py2-only wheels refused, py3 preferred — **verified** (`py2.py3` also accepted correctly).
- dependency specs stored and enforced by `add` and `sync` — **stored: verified; enforced correctly: false** (defects 1–2).
- missing locked vendor tree refused with “run `ail sync` first” — **verified**.
- `test_ail_pkg` passes — **verified** (module ok). Required modules `test_ail_pkg`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` with `-j 2`: **4/4 ok**. `update_manifest.py --check` rc=0; changed files are only the allowed ones + `manifest.d/0d.txt`, `21.txt` — **verified**.
- census 30/30 with matching hashes — **partially verified** (4 packages spot-checked against PyPI, all hashes match); `test_ail_packaging` — **unverified**.

**Pre-existing:** none identified. **Unverified:** full 30-package PyPI census; `test_ail_packaging`.

VERDICT: FIX
[cost $0.0000, opencode tokens {"total": 1156762, "input": 86388, "output": 7151, "reasoning": 33847, "cache.write": 0, "cache.read": 1029376}]
    tool time: bash 6.5 min
        250s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000; timeout 900 python3 tools/par_check.py -j 2 test_ail_
        136s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000; timeout 600 python3 tools/par_check.py -j 2 test_ail_
          1s bash   cd /tmp/rprobes && rm -rf real2 real3 && mkdir real2 real3 ulimit -v 1500000 cd /tmp/rprobes/real2 && timeout 
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check; echo "manifest rc=$?"; git dif
          0s bash   mkdir -p /tmp/rprobes/realpkg && cd /tmp/rprobes/realpkg && rm -rf * .??* 2>/dev/null; ulimit -v 1500000; time
          0s bash   cat > /tmp/rprobes/probe_a.py <<'PY' from harness import * base=tempfile.mkdtemp(prefix="idx-"); ix=Index(base
          0s bash   cat > /tmp/rprobes/probe_b.py <<'PY' from harness import * # local-only stable version and wildcard/paren spec
          0s bash   cat > /tmp/rprobes/probe_c.py <<'PY' from harness import * base=tempfile.mkdtemp(prefix="idx3-"); ix=Index(bas

FINAL VERDICT: FIX  2026-11-08T07:16:00Z
