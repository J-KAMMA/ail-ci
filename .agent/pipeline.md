# job job-guide1-11041433  started 2026-11-04T05:34:56Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done. Commit `dc906f6` on `job-guide1-11041433` (not pushed, per the standing rules).

- Added `docs/guide/` README plus 4 chapters: **42 samples** total (12 / 10 / 10 / 10).
- `AIL_CURRENT/test_ail_guide.py` builds and runs every sample, compares stdout and exit status with CPython 3.12, and checks `general`, `refuse`, `stop`, and `exact` modes.
- Registered the test in `tests.d`; `tools/update_manifest.py --check` passes.
- Tests run: `test_ail_guide` 44 tests OK (42 samples); `test_ail_files` OK; `test_ail_corpus_findings3` OK; `test_ail_safetynet` 5 OK without a memory limit (under `ulimit -v 1500000` its `S4_generators_gc` case truncates output).
- Probes covered stdin/stdout, bytes, file I/O, argv, exceptions, int64 overflow, exact ints, general-path notes, stdlib modules, and the libm `cbrt` FFI sample; all matched CPython or were refused as documented.
- Only the allowed guide files, test files, and manifest pins changed.
[cost $0.0000, opencode tokens {"total": 2443998, "input": 49327, "output": 20620, "reasoning": 18339, "cache.write": 0, "cache.read": 2355712}]
    tool time: bash 11.2 min, write 0.0 min, read 0.0 min
        327s bash   cd /home/runner/work/_temp/w2 && ulimit -v 1500000; for t in test_ail_guide test_ail_safetynet test_ail_files 
        143s bash   cd /home/runner/work/_temp/w2 && python3 -B AIL_CURRENT/test_ail_safetynet.py 2>&1 | tail -25
         84s bash   cd /home/runner/work/_temp/w2 && ulimit -v 1500000; python3 -B AIL_CURRENT/test_ail_safetynet.py 2>&1 | tail -
         40s bash   cd /home/runner/work/_temp/w2 && ulimit -v 1500000; python3 AIL_CURRENT/test_ail_guide.py 2>&1 | tail -80
         25s bash   cd /tmp/probes2 && cat > c4_math.py <<'EOF' import math  def main() -> None:     print(math.sqrt(81.0))     pr
         17s bash   mkdir -p /tmp/probes && cd /tmp/probes && cat > p_stdin.py <<'EOF' import sys  def main() -> None:     n: int 
          9s bash   cd /tmp/probes && cat > p_file.py <<'EOF' def main() -> None:     with open("guide_tmp.txt", "w") as f:       
          6s bash   cd /tmp/probes && cat > p_file.py <<'EOF' def main() -> None:     with open("guide_tmp.txt", "w") as f:       

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change does.** Adds `docs/guide/` (README + 4 chapters, 42 samples: 12/10/10/10), `AIL_CURRENT/test_ail_guide.py` (tutorial parser plus stdin/mode checks), `tests.d` registration, and two manifest shards. No compiler or runtime change.

**Verified.**
- `test_ail_guide.py`: 44 tests OK (42 samples); under `par_check.py -j 2`: OK.
- `test_ail_files` and `test_ail_corpus_findings3`: OK. `test_ail_safetynet`: 5 OK without the memory limit.
- `tools/update_manifest.py --check`: exit 0; `git diff work..HEAD` contains only allowed paths.
- Extra probes for int64 `+`/`-` overflow, stdin newlines, exact big ints, `argv[0]`, and refusals match CPython or are refused as documented.
- Worker report's counts (42, 12/10/10/10, 44, manifest) are correct.

**Defects.**
1. `docs/guide/03-errors-and-exit.md:3` says "there is no bare `except`". False: `/tmp/rprobes/bare_except.py` (a `try` with `except:`) builds with `--strict` on HEAD and on base `b796a01`, runs, and prints `caught` with exit 0. Expected per the guide: bare `except` unavailable; actual: supported. The claim is also not shown by any sample or citation.
2. `docs/guide/01-typed-and-general.md:264` lists `import numpy` among refusals that the preceding paragraph says exit 3. `/tmp/rprobes/refuse_numpy.py` is refused, but with exit status 2 (both builds), not 3. Expected per text: 3; actual: 2.

**Minor.**
- `docs/guide/README.md:3` says every sample is run and its stdout compared byte-for-byte with CPython; the `refuse` sample is not run, and the two `stop` samples' stdout is compared with the page, not CPython.
- `docs/guide/01-typed-and-general.md:155` shows "about 20x slower", a speed number not quoted or linked from `docs/COMPARISON.md`, contrary to the task's text rule (unless compiler-verbatim output is exempt).

**Pre-existing.**
- `test_ail_safetynet` `S4_generators_gc` truncates under `ulimit -v 1500000`; reproduced identically on base `b796a01`. No runtime files changed.

VERDICT: FIX
[cost $0.0000, opencode tokens {"total": 1442788, "input": 65651, "output": 6330, "reasoning": 38199, "cache.write": 0, "cache.read": 1332608}]
    tool time: bash 9.2 min
        194s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && ls test_ail_corpus_findings3.py test_ail_files.py test_ail_guide.
        143s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && date; timeout 600 python3 ../tools/par_check.py -j 2 test_ail_saf
         82s bash   cd /tmp/baseguide/AIL_CURRENT && date; ulimit -v 1500000; timeout 600 python3 ../tools/par_check.py -j 2 test_
         81s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && date; ulimit -v 1500000; timeout 900 python3 ../tools/par_check.p
         40s bash   cd AIL_CURRENT && ulimit -v 1500000; timeout 900 python3 test_ail_guide.py 2>&1 | tail -80
          4s bash   cd /tmp/rprobes && cat > json_noann.py <<'EOF' import json   def main() -> None:     data = json.loads('{"a": 
          2s bash   cd /home/runner/work/_temp/w2 && date; for p in bare_except stdin_newline; do echo "=== $p ==="; if [ "$p" = s
          2s bash   cd /tmp/rprobes && cat > exact_probe.py <<'EOF' def main() -> None:     print(-9223372036854775808)     print(

## worker report 1
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Fixed and committed as `e727f2d`.

**Defects fixed**
1. Removed the false “there is no bare `except`” claim from `03-errors-and-exit.md`; a probe shows bare `except` builds and runs.
2. Moved `import numpy` out of the exit-3 refusal list into a `missing` sample that documents its real exit status (2); added that mode to `test_ail_guide.py`.
3. Corrected `README.md` (and the test docstring) to say only samples that build are run, and that run-time-stop samples are checked against the shown text rather than CPython.
4. Removed the unquoted “about 20x slower” number from the note block; the text now says the compiler adds its own estimate and the guide omits it.

**Tests (final commit)**
- `test_ail_guide.py`: 45 tests OK, **43 samples** (13/10/10/10).
- `test_ail_files`: OK (79.7s).
- `test_ail_corpus_findings3`: OK (190.7s).
- `test_ail_safetynet`: 5 OK without the memory limit; `S4_generators_gc` truncates under `ulimit -v 1500000` (pre-existing, reproduced on base).
- `tools/update_manifest.py --check`: exit 0.
- `git diff --stat b796a01`: only the 9 allowed files.

**Probes** (`bash ~/tools/cmp.sh`)
- `bare_except.py`: CPython exit 0; both builds exit 0, same stdout — claim removed.
- `imp_numpy.py`: both builds refuse with exit 2 and the shown message; CPython raises `ModuleNotFoundError`.
- `general_dict.py`: both builds match CPython stdout; note line present.

Did not push, per the standing rules.
[commandcode stop=end_turn turns=26 out_tokens=13011]

## review 1 skipped: only 11 minutes left

FINAL VERDICT: FIX  2026-11-04T10:18:16Z
