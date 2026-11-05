# job job-relver1-11051130  started 2026-11-05T02:34:34Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done. Committed on `job-relver1-11051130` (5 commits, not pushed per the repo rule).

**Changes**
- `AIL_CURRENT/test_ail_version_consistency.py` — 7 test methods; registered via `AIL_CURRENT/tests.d/test_ail_version_consistency.txt`; manifest refreshed (`--check` clean).
- `docs/LSP.md:71` — sample version now `0.1.0.dev0` (matches `__version__`).
- `docs/RELEASING.md` — 32 lines: single source, proof command, owner-gated tag/publish.
- Manifest files: `AIL_CURRENT/manifest.d/4f.txt`, `7a.txt`.

**Verification**
- `python3 AIL_CURRENT/test_ail_version_consistency.py`: 7 tests, OK.
- Scratch bump `__version__ 0.1.0.dev0 -> 0.1.0`: exactly 1 failure (`docs/LSP.md:71` stale literal); restoring passes.
- Inventory: type-(a)/(b)/(c) list recorded in first commit body; 0 type-(b) disagreements remain.
- `test_ail_packaging`, `test_ail_quickstart_docs`, `test_ail_files`, `test_ail_corpus_findings3`: pass.
- `test_ail_safetynet`: passes without the 1.5 GB ulimit; under `ulimit -v 1500000` it fails `S4_generators_gc` (memory cap, no compiler change). Direct S4 passes uncapped.
- Changed files vs base: exactly the 6 allowed files.

Not done: push/PR and the 20 CI shards, because the standing rules forbid pushing and reserve the suite for CI.
[cost $0.0000, opencode tokens {"total": 2038729, "input": 83512, "output": 8638, "reasoning": 18643, "cache.write": 0, "cache.read": 1927936}]
    tool time: bash 16.5 min, edit 0.0 min, write 0.0 min
        515s bash   ulimit -v 1500000; python3 tools/par_check.py -j 2 test_ail_version_consistency test_ail_packaging test_ail_qu
        235s bash   python3 tools/par_check.py -j 1 test_ail_safetynet 2>&1 | tail -8
        159s bash   ulimit -v 1500000; python3 tools/par_check.py -j 1 test_ail_safetynet 2>&1 | tail -25
         70s bash   python3 - <<'PY' import sys sys.path.insert(0, 'AIL_CURRENT') import test_ail_safetynet as t name, text, stdin
          4s bash   ulimit -v 1500000; python3 tools/par_check.py -j 2 test_ail_version_consistency test_ail_quickstart_docs 2>&1 
          2s bash   rm -rf /tmp/relver-scratch && mkdir -p /tmp/relver-scratch && tar -cf - --exclude=.git . | tar -xf - -C /tmp/r
          1s bash   rm -rf /tmp/relver-scratch && mkdir -p /tmp/relver-scratch && tar -cf - --exclude=.git . | tar -xf - -C /tmp/r
          1s bash   python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/test_ail_version_consistency.py') s=p.read_text(

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: relver1

**What the change really does (one line):** adds `test_ail_version_consistency.py` (7 checks: PEP 440 source version, dynamic pyproject, `ailc <version>`, wheel name, METADATA, docs literals, dated WHEEL_REPORT), rewrites the `docs/LSP.md` sample from `0.1.0` to `0.1.0.dev0`, adds a 32-line `docs/RELEASING.md`, and repins the two manifest shards. No compiler or runtime code is touched.

**Probes (`/tmp/rprobes`, plus scratch copies):**

| Probe | Result |
|---|---|
| `hello.py`, `lspver.py` via `cmp.sh` on HEAD | `g` and `d` both match CPython |
| `hello.py` on `/tmp/base` | matches CPython both builds |
| `program.c` with `--debug-dir`, HEAD vs base | byte-identical (only temp paths differ in `native_report.json`) |
| Scratch bump `__version__` `0.1.0.dev0`→`0.1.0` | exactly 1 failure: `docs/LSP.md:71: 0.1.0.dev0` (matches report); restore → OK |
| Force `docs/LSP.md` stale on HEAD | 1 failure, names `docs/LSP.md:71` |
| Add `AIL version: 0.1.0` / `The AIL version is 0.1.0` to README | caught (fails) |
| Add `Current release: 0.1.0` / `Release 0.1.0 is out` | **not caught** (keyword-gated scan) |
| Add stray `9.9.9` to WHEEL_REPORT | not caught (whole-file dated exemption) |

**Tests run on HEAD (`par_check -j 2`):** `test_ail_version_consistency`, `test_ail_packaging`, `test_ail_quickstart_docs`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — all 6 pass. `update_manifest.py --check` exit 0. Diff is exactly the 6 permitted files.

**Report claims:** 7 test methods verified; LSP line updated verified; RELEASING 32 lines verified; manifest refresh verified; scratch-bump exactly 1 failure verified; inventory categories consistent with my grep; 0 current type-(b) disagreements verified (WHEEL_REPORT is the only other literal and is historical); files/packaging/quickstart/safetynet pass verified; exactly 6 files vs base verified. The 20 CI shards and the claimed `ulimit` S4 safetynet failure were not re-run (unverified; no compiler change, so pre-existing either way).

**Notes (non-blocking):** the docs scanner only inspects lines containing `ail`/`version`, so a stale literal on a line without either word escapes it; the WHEEL_REPORT exemption is report-wide rather than per-line, but WHEEL_REPORT is not in the editable allowlist, so coupling the date to each version line is not achievable without touching a forbidden file. The task's description of line 71 as a `serverInfo` reply is inaccurate — it is the sample VS Code `package.json` version — but the task explicitly permitted using the real value there, and it now agrees with `__version__`.

**Pre-existing:** none observed; HEAD and base compile `hello.py` to identical C and both match CPython.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 660891, "input": 50125, "output": 4813, "reasoning": 15617, "cache.write": 0, "cache.read": 590336}]
    tool time: bash 8.5 min
        247s bash   date; cd /home/runner/work/_temp/w2 && timeout 900 python3 tools/par_check.py -j 2 test_ail_version_consistenc
        247s bash   date; cd /home/runner/work/_temp/w2 && timeout 600 python3 tools/par_check.py -j 2 test_ail_files test_ail_cor
          5s bash   date; cd /tmp && bash ~/tools/cmp.sh /tmp/rprobes/hello.py /home/runner/work/_temp/w2 2>&1 | tail -12; echo ==
          4s bash   cd /tmp && bash ~/tools/cmp.sh /tmp/rprobes/lspver.py /home/runner/work/_temp/w2 2>&1 | tail -10
          1s bash   cd /tmp/rscratch && cp README.md /tmp/readme.bak && for case in 'Current release: 0.1.0' 'AIL version: 0.1.0' 
          1s bash   date; cd /home/runner/work/_temp/w2 && python3 AIL_CURRENT/test_ail_version_consistency.py 2>&1 | tail -20; py
          0s bash   cd /home/runner/work/_temp/w2 && git worktree add /tmp/base work 2>&1 | tail -3; ls /tmp/base | head -3; mkdir
          0s bash   cd /home/runner/work/_temp/w2 && python3 tools/update_manifest.py --check; echo "manifest exit=$?"; grep -n 't

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-05T04:23:35Z
