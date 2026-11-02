**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model opencode-go/deepseek-v4.1-flash]
## Review

**Diff summary.** The change adds `AIL_CURRENT/ail.py` (CPython versions of the AIL-only built-ins), makes `python_surface` drop `from ail import …` / rewrite `ail.X`, stops `ail_modules` merging `ail`, makes `tools/ail2py.py` emit the import, and adds the CPython parity script and tests. It does what the report says structurally.

**Verified claims**
- Converter `--check --flags "--strict"`: `identical` for all ten tasks (ran all ten).
- `tools/ail2py_cpython_check.py`: nine tasks `mismatches 0`; `tally_lang 75 cases mismatches 1 ['hidden/long_unary_chain']`.
- `from ail import wrapping_add` builds `program.c` identical to the bare program; `import ail` + `ail.wrapping_add` also identical. A program containing “ail” but no import has C identical to base.
- `jscharat` astral, `path_exists`/`is_dir` ENOENT/ENOTDIR/empty, codecs, wrapping, heap equal-key order, stdin, `read_bytes`/`file_chunks` aliasing probes all match the AOT build.
- `test_ail_ail2py`, `test_ail_python_syntax`, `test_ail_heapq_bisect`, `test_ail_overflow_error`, `test_ail_builtin_contracts`, `test_ail_api_profiles`, `test_ail_files`, `test_ail_corpus_findings3` pass; `test_ail_safetynet` passes without the VM cap. `update_manifest.py --check` exits 0.
- “Fixed all three defects”: **false for `same_file`** (see defect 1); the other two fixes are correct.

**Defects (new)** — full probe files in `/tmp/rprobes/`

1. `/tmp/rprobes/rv_same2.py` — `same_file` short-circuits when the first path is missing and never stats the second. The runtime (`ail_same_file`, cruntime.py:26246) calls `ail_file_identity` on both paths before checking. Expected (AIL binary): `miss-empty OSError`, `miss-enotdir OSError`; actual (`ail.py:393`): `miss-empty 0`, `miss-enotdir 0`. This contradicts the report’s “empty path and non-ENOENT stat failures raise OSError”.
2. `/tmp/rprobes/rv_close2.py` — `_BinaryFile` methods dereference `self._file` after `close()` sets it to `None` (`ail.py:35-76`). The runtime `ail_binaryfile_ready` raises `ValueError`. Expected (AIL binary): `read ValueError`, exit 0; actual (CPython/`ail.py`): `AttributeError: 'NoneType' object has no attribute 'read'`, exit 1. Same for `readinto/write/seek/tell/flush`.
3. `/tmp/rprobes/rv_alias.py` — `from ail import wrapping_add as w` is dropped but the alias is not rewritten or refused (`ail_syntax.py:4127`). Expected under CPython: `3`; actual AIL compile: `not in the subset: the name 'w' is not a known function/class/builtin`.

**Pre-existing**
- `AIL_UNIFIED_FORCE=1` refuses the AIL-only built-ins on both base and HEAD (base fails at the import, HEAD at the built-in name; both named refusals).
- `test_ail_safetynet` `S4_generators_gc` fails under `ulimit -v 1500000` identically on base and HEAD; passes without the cap.

**Unverified**
- TCP (`tcp_connect/listen/poll/accept/recv/send`) parity was not exercised.
- `current_dir`/`monotonic_ms` exact values are not comparable.
- Speed: no runtime/codegen hot path changed, so no `icount` run.

VERDICT: FIX

1. Fix `same_file` to evaluate both identities before returning 0 (probe `rv_same2.py`; expected `miss-empty OSError`, `miss-enotdir OSError`, actual `0`).
2. Make `_BinaryFile` methods raise `ValueError` after `close()` (probe `rv_close2.py`; expected `read ValueError`/exit 0, actual `AttributeError`/exit 1).
3. Handle or refuse `from ail import X as Y` instead of dropping the alias (probe `rv_alias.py`; expected `3`, actual compile failure on `w`).
[cost $0.0571, opencode tokens {"total": 4153598, "input": 118574, "output": 12115, "reasoning": 33405, "cache.write": 0, "cache.read": 3989504}]
    tool time: bash 9.9 min, write 0.0 min
        143s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && ulimit -v 1500000 && timeout 900 python3 ../tools/par_check.
        140s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 1 test_ail_saf
         78s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && ulimit -v 1500000 && timeout 1200 python3 ../tools/par_check
         77s bash   cd /tmp/base/AIL_CURRENT && ulimit -v 1500000 && timeout 1200 python3 ../tools/par_check.py -j 1 test_ail_safe
         61s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000 && PYTHONPATH=$PWD/AIL_CURRENT timeout 600 python3 -B 
         58s bash   cd /home/runner/work/ail-ci/ail-ci && for t in berth_sim chain_relax echo_pack ledger_bin rail_transfer scar_l
         14s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && ulimit -v 1500000 && timeout 900 python3 ../tools/par_check.
          9s bash   cd /home/runner/work/ail-ci/ail-ci && export PYTHONPATH=$PWD/AIL_CURRENT RV_SET_XYZ=setval && ulimit -v 150000


--- ORIGINAL TASK ---
Lane: frontend

**Owner decisions (2026-11-03):** AIL is one language, Python syntax plus optional annotations. The compare-lab `ail` column may use the converted annotated `typed.py` when its C is identical, and the plain `main.py` stays as its own row. The brace front end is removed before the 0.1 tag. AIL-only built-ins are spelled `from ail import ...`.

# onelang s2: the `ail` module for AIL-only built-ins; converted files run under CPython

Time budget: 80 minutes. Commit and push after each sub-step.

**Number this moves:** for the ten compare-lab tasks, the converted file (`tools/ail2py.py`) (a) still builds to a
`program.c` byte-identical to its `.ail`, and (b) run by `python3` gives the same stdout and exit code as
`reference.py` on every public and hidden case: today 8/10 tasks fail under CPython only because names like
`read_stdin_bytes` or `wrapping_add` do not exist there, and rail_transfer uses `heappush(h, x, key=...)`. Target:
10/10 tasks, all cases, except the one listed case `tally_lang hidden/long_unary_chain` (CPython recursion limit).

Base: `origin/integ` after onelang s1 merged.

## Sub-steps

1. **`AIL_CURRENT/ail.py`**: a pure-Python module that defines, with CPython code that behaves as the AIL built-in does,
   every name in Appendix C. Read each built-in's behaviour from `AIL_CURRENT/ail_builtin_api.py` (`DECLARATIONS`) and
   its C in `AIL_CURRENT/python/pkg-v12/cruntime.py`; where unsure, write a probe program, build it with the compiler
   and copy what the binary does (stdout, exit code, exception type). `heappush(h, x, key=None)` /
   `heappop(h, key=None)`: a binary heap ordered by `key(x)` (by `x` when `key` is None); with equal keys it must
   pop in the same order as the AIL runtime (probe with equal keys and copy that order). `par_range = range`.
   `wrapping_add/sub/mul(a, b)`: the int64 wrap `((r + 2**63) % 2**64) - 2**63`. Commit, push, open the PR.
2. **Compiler recognises `from ail import X`.** In `python_surface` (or the `_Surface` import handling in
   `AIL_CURRENT/ail_syntax.py`): a top-level `from ail import a, b` whose names are all AIL built-ins is replaced by a
   blank line (keep line numbers) and binds nothing else; `import ail` + `ail.X(...)` is rewritten to `X(...)`. A name
   that is not an AIL built-in is refused by name (`ail has no X`). `ail_modules.merge_program` must not merge `ail.py`
   (add `ail` to whatever list keeps `ail_array`/`ail_ffi` out). Probe: a program with `from ail import
   wrapping_add` builds to the same `program.c` as the same program without the import line. Commit, push.
3. **Converter writes the import.** `tools/ail2py.py` adds `from ail import <sorted names>` after the `from m import *`
   lines for every AIL-only built-in the file calls (Appendix C names). Commit, push.
4. **CPython parity run** (Appendix D). For tally_lang, add nothing to the program: the one case is listed as a known
   CPython limit. Commit `tools/ail2py_cpython_check.py` (the script of Appendix D), push.
5. Test: extend `AIL_CURRENT/test_ail_ail2py.py`: `from ail import ...` program C equals the bare program's C (via
   `--debug-dir` and `cmp`); `ail.heappush` with equal keys matches the AOT binary; `ail.wrapping_mul` of two values near
   2**62 matches the AOT binary. `tools/update_manifest.py`, `--check`. Commit, push.

## Done-check

- `python3 -B tools/ail2py.py lab/compare/src/$t/main.ail --check --flags "--strict"` prints `identical` for all ten.
- `python3 -B tools/ail2py_cpython_check.py` prints `mismatches 0` for nine tasks and `mismatches 1
  (hidden/long_unary_chain)` for tally_lang.
- `tools/par_check.py -j 2 test_ail_ail2py test_ail_python_syntax test_ail_heapq_bisect test_ail_overflow_error` passes;
  all 20 shards pass.

## Stop rule

Stop if: dropping the import line changes any `program.c`; an `ail.py` function cannot be made to match the binary on a
probe (list it, leave it out, the converter then keeps the bare name); a compiler change outside the files named here would be needed; any compare-lab `program.c` changes; any listed test module fails for a reason the base did not have; or 80 minutes pass. Push what is green and report. Do not touch `.github/workflows`.

## Appendix A: standing rules

1. No regressions: a program that built and matched CPython before must still do so in the default build.
2. Probe ints beyond int64 wherever ints come from text or arithmetic; run probes in the default build and with
   `AIL_UNIFIED_FORCE=1`, compare both with `python3`.
3. Push early, open the PR against `integ`, wait for all 20 `shard` checks (`gh pr checks <n> -R J-KAMMA/ail-ci`, at most
   once every 10 minutes). Report only when all pass, or say which fail and why.
4. Branch from `integ` (or one unmerged PR at most).
5. Memory: wrap heavy runs in `ulimit -v 1500000`; `tools/par_check.py -j 2` at most; leave no background jobs.
6. New test module: `AIL_CURRENT/tests.d/<module>.txt` if the directory exists, else `ail_check.py` MODULES; `git add`,
   `tools/update_manifest.py`, then `--check`.
7. Never print credentials, run a broad pkill, merge PRs, change repository settings, cancel runs, or edit
   `.github/workflows`.

## Appendix C: AIL-only built-ins for `ail.py`

Free functions declared in `ail_builtin_api.DECLARATIONS` that CPython does not have: `append_bytes current_dir
file_size float64_decode float64_encode flush_stdout get_env integer_decode integer_encode is_dir jscharat jsdiv
jsnegzero list_dir make_dir monotonic_ms open_binary path_exists pcm16_scale_le read_bytes read_stdin_bytes remove_dir
remove_file replace_path same_file tcp_connect tcp_listen tcp_poll wrapping_add wrapping_mul wrapping_sub write_bytes
write_stdout_bytes write_text`, plus `heappush heappop` (with `key=`), `par_range`, and `file_chunks` if the compiler
builds it as a built-in (check). The handle types (`binaryfile`, `tcpsocket`) are what `open_binary`/`tcp_*` return:
give `ail.py` small classes with the declared methods (`read seek tell write flush close closed`; `accept recv send
close ...`). compare-lab needs: `heappush heappop read_bytes read_stdin_bytes wrapping_add wrapping_mul
write_stdout_bytes`.

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT [--syntax python] [--strict] [--debug-dir DIR]`;
  `DIR/program.c` is the generated C; `--strict` = typed path or refuse. `-o` must not exist yet.
- Brace front end: `AIL_CURRENT/ail_syntax.py` `detect()` (about line 206) and `translate()` (about line 285), which
  turns brace text into annotated Python text (`-> R` becomes `-> __ail_checked_R__`). `python_surface()` (about line
  4101) maps Python spellings onto the compiler's built-ins. The per-file loader is `load()` in
  `AIL_CURRENT/ail_chatgpt.py` (about lines 4908-5190; `syntax == 'ail'` branches there are brace-only checks).
- `use m` resolves `AIL_CURRENT/language_examples/m.ail` (`standard = ROOT / 'language_examples'`, about line 4897 of
  ail_chatgpt.py). Python `from m import *` is merged by `AIL_CURRENT/ail_modules.py` `merge_program`, which renames
  `m.f` to `m__f` in the C.
- The converter (onelang s1-s3): `python3 tools/ail2py.py SRC.ail [-o OUT.py] [--check [--flags "..."]]`; `--check`
  prints `identical` / `identical-renamed` / `differ ...` / `py-refused ...` / `both-fail`.
- compare-lab: `lab/compare/src/<task>/main.ail` (brace) and `main.py` (plain CPython program; the pyreach line works on
  these); `lab/compare/run_task.py` (`LANGS`, `SOURCE` map about line 33, `build_cmd` about line 58,
  `EXACT_INT_TASKS = ('rail_transfer', 'chain_relax')`, cold builds with a fresh `AIL_CACHE`, `compile_s` = median).
  Tasks: berth_sim chain_relax echo_pack ledger_bin rail_transfer scar_life tally_lang term_rank ticket_audit tree_fold.
- Census of 2026-11-03 (integ f6d5825c): 391 tracked `.ail` (268 `AIL_CURRENT/language_examples`, of which 262 brace and
  137 entry programs; 10 compare-lab; 109 `lab/syntax/runs` experiment records; 4 `lab/flags/programs`, Python text);
  147 test modules embed brace sources (699 `fn main(`), 37 test modules read `language_examples/`, 46 hash
  `pyfunc.to_c(...)` codegen pins.

## Appendix D: CPython parity script (`tools/ail2py_cpython_check.py`)

```python
import sys, subprocess, tempfile
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'lab/compare')); import run_task
for t in sys.argv[1:] or 'berth_sim chain_relax echo_pack ledger_bin rail_transfer scar_life tally_lang term_rank ticket_audit tree_fold'.split():
    work = Path(tempfile.mkdtemp(prefix='a2p-')); conv = work / 'main.py'
    subprocess.run([sys.executable, '-B', str(REPO / 'tools/ail2py.py'), str(REPO / f'lab/compare/src/{t}/main.ail'),
                    '-o', str(conv)], check=True)
    run_task.CURRENT_TASK = t
    check = run_task.make_check_cases(t, work); expected = run_task.reference_outputs(t, check, work)
    env_cmd = [sys.executable, '-B', str(conv)]
    bad = []
    for kind, name, case in check:
        out = work / 'o.out'
        p = run_task.exec_prog([], env_cmd, case, out, 60)    # PYTHONPATH must contain AIL_CURRENT (for ail.py)
        if (p.returncode, out.read_bytes()) != expected[(kind, name)]:
            bad.append(f'{kind}/{name}')
    print(t, 'cases', len(check), 'mismatches', len(bad), bad[:3])
```
Run it as `PYTHONPATH=$PWD/AIL_CURRENT python3 -B tools/ail2py_cpython_check.py` inside `ulimit -v 1500000`.

**Rules for every job.**
- **Load:** you are one of up to five agents on a 16 GB PC. Keep local parallelism at 2 (`-j 2`) and never run the whole suite; the full suite runs on CI after merge.
- **Commits:** commit with explicit `git add` on your branch. Messages end with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- **Forbidden:** push, stash, rebase, reset, and deletion outside /tmp.
- **Records:**
  - New DIFFERENCES rows use placeholder ids `C?-<your branch>-N`.
  - Add a DEVLOG entry at the top with today's date.
  - Register a new test module: if `AIL_CURRENT/tests.d/` exists, add `AIL_CURRENT/tests.d/<module>.txt` containing the module
    name and do NOT edit the tuple in `ail_check.py`; otherwise append it to the `MODULES` tuple.
  - `git add` new files, run `python3 tools/update_manifest.py`, then `--check`. Do not hand-edit `MANIFEST.json` or `manifest.d/`.
- **Required tests:** the targeted modules for what you touch, plus test_ail_safetynet, test_ail_files and test_ail_corpus_findings3. Run them on your final commit, not an earlier one.
- **Mandatory self-check before you report.** A reviewer will repeat it, and past reports were wrong about half the time.
  1. Write probe programs in /tmp/probes/ for every behaviour you changed. Cover the boundaries your implementation implies, not only the example: types, widths, empty, negative, aliasing, values reaching the code through an argument, a list item, an attribute and a dict value, and both builds.
  2. Run each probe with `bash ~/tools/cmp.sh /tmp/probes/<p>.py $PWD`.
  3. Every probe must match CPython or be refused by name.
  4. List the probes and their results in the report.
- **Never claim something works unless a probe or test you ran shows it.** If you did not verify something, say so.
- **Tokens:** use grep -n, narrow reads, and `tail` on long logs.
- **Budget:** stop at the budget note, leaving a committed, consistent state.
- **Report:** keep it brief, with numbers.
- Test data: email addresses only on example.com / example.org (the public export audit rejects any other domain).

**Work in few steps** (each step costs model time):
- Write all probe programs first, then run them together with one command, for example a loop over `bash ~/tools/cmp.sh`, instead of one command per program.
- Search only inside the repository (`grep -rn ... AIL_CURRENT tools`), never across `/home` or `/tmp`.
- Read a file once, using a range that is large enough, instead of many small reads.
- Do not re-run a test that already passed unless you changed code since.

**Where you run:** a GitHub Actions runner (4 cores). Commit your work on the current branch; do not push.
