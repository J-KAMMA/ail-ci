**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model opencode/deepseek-v4.1-flash-free]
## Review 3

**Diff summary.** `same_file` now stats both paths before returning 0, `_BinaryFile` methods raise `ValueError` after `close()`, and `from ail import X as Y` rewrites loads of `Y` to `X` while refusing later rebinding. Tests, DEVLOG and manifest hashes are updated. The structure matches the report, except that “any later rebinding” is not fully enforced.

**Verified claims**
- `same_file` probe (`same_typed2.py`): HEAD `d` matches CPython; base differs at `miss-empty`/`miss-enotdir` (`0` vs `OSError`). Fixed.
- `close_typed.py`: HEAD matches CPython; base raises `AttributeError` after close. Fixed.
- `alias_calls.py`, `alias_list.py`, `alias_nested.py`, `alias_unicode.py`, `import_ail.py`, `import_ail_alias.py`: match CPython in both builds; alias/`import ail` C is byte-identical to the bare program.
- All 11 rebinding forms (assign, for, with, lambda, def, arg, except, match, import, from-import, `import ail`) refuse with `ail import alias w is rebound` in both builds.
- `test_ail_ail2py` 10/10 OK; `test_ail_safetynet`, `test_ail_python_syntax`, `test_ail_files`, `test_ail_corpus_findings3` pass.
- All ten converter `--check --strict` print `identical`.
- `ail2py_cpython_check.py`: nine tasks `mismatches 0`; `tally_lang` only `hidden/long_unary_chain`.
- `update_manifest.py --check` exits 0.

**Defect**

1. `/tmp/rprobes/r3/alias_rebind_same_import.py` — a second `from ail import ... as` binding the same alias is not refused, and earlier loads are silently rewritten to the later target.
   ```python
   from ail import wrapping_add as w
   print(w(1, 2))
   from ail import wrapping_mul as w
   print(w(3, 4))
   ```
   Expected (CPython): `3`, then `12`. Actual (HEAD, both default and unified): `2`, then `12`, exit 0. Base refused the program by name, so this is introduced by the change. Cause: `from_aliases[asname]` is overwritten for each top-level `from ail` import, while the rebinding check exempts every dropped `from ail` alias. Fix: refuse a second binding of an alias whose source name differs (or resolve aliases by source position).

**Pre-existing**
- `from ail import wrapping_add; wrapping_add = 3; wrapping_add(1, 2)`: both base and HEAD silently print `3`, CPython raises `TypeError`.
- `AIL_UNIFIED_FORCE=1` refuses the AIL-only built-ins by name on base and HEAD.
- Untyped `same_file` probes are refused identically on base and HEAD (the built-in needs the typed/general path).

**Unverified:** TCP parity, exact `current_dir`/`monotonic_ms` values, and speed (only frontend/CPython-module code changed, no codegen or runtime hot path).

VERDICT: FIX
1. Refuse (or positionally resolve) a repeated `from ail import ... as Y` alias; probe `alias_rebind_same_import.py`, expected `3`/`12`, actual `2`/`12`.
[cost $0.0000, opencode tokens {"total": 1209095, "input": 51224, "output": 8883, "reasoning": 17724, "cache.write": 0, "cache.read": 1131264}]
    tool time: bash 11.3 min
        234s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1500 python3 ../tools/par_check.py -j 2 test_ail_pyt
        179s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1500 python3 ../tools/par_check.py -j 2 test_ail_ail
         98s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000 && PYTHONPATH=$PWD/AIL_CURRENT timeout 1200 python3 -B
         96s bash   cd /home/runner/work/ail-ci/ail-ci && for t in berth_sim chain_relax echo_pack ledger_bin rail_transfer scar_l
         14s bash   cd /tmp/rprobes/r3 cat > alias_rebind_for.py <<'EOF' from ail import wrapping_add as w for w in [1, 2]:     pr
         12s bash   cd /home/runner/work/ail-ci/ail-ci; export PYTHONPATH=$PWD/AIL_CURRENT; for p in /tmp/rprobes/r3/*.py; do echo
          8s bash   cd /home/runner/work/ail-ci/ail-ci; export PYTHONPATH=$PWD/AIL_CURRENT; for p in /tmp/rprobes/r3/same_typed.py
          7s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 600 python3 test_ail_ail2py.py 2>&1 | tail -8


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
