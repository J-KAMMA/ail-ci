Lane: typeshed

# typeshed1: vendor a pinned typeshed stdlib subset and turn its `.pyi` stubs into a signature table (no compiler change yet)

Time budget: 80 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** stdlib call sites in `lab/census/programs/` (686 programs) whose callee has a known signature
in an AIL table. Today it is 0: the compiler has no stdlib signature data. `typeshed1` makes the table and the counter;
`typeshed2` makes the compiler read it. Report two numbers:
- `known`: call sites `mod.f(...)` / `from mod import f; f(...)` of a stdlib module whose `mod.f` is in the table;
- `scalar`: the part of `known` whose return is exactly `int`, `float` or `bool` (what the general path can unbox).
Also report `total` (all stdlib call sites the counter sees). Target: `known >= 60%` of `total` for the modules in the
vendored list. A grep on 2026-11-04 found about 300 such call sites (`re.compile` 36, `json.dumps` 32, `random.seed` 24,
`heapq.heappush` 19, `math.sqrt` 8, `math.isqrt` 4, `math.gcd` 4, `statistics.median` 4, ...).

Base: `origin/integ`. Files you may create or edit, and no others:
- `third_party/typeshed/` (new): `LICENSE` (typeshed's own file, unchanged), `VERSION.md`, `stdlib/<module>.pyi`
  (only the modules listed in `VERSION.md`, plus `builtins.pyi`)
- `tools/typeshed_convert.py` (new): `.pyi` -> table
- `AIL_CURRENT/python/pkg-v12/stubsigs_table.py` (new, generated, never hand-edited)
- `AIL_CURRENT/python/pkg-v12/stubsigs.py` (new): the lookup API
- `tools/typeshed_reach.py` (new): the corpus counter
- `lab/typeshed/RESULTS.md` (new)
- `AIL_CURRENT/test_ail_stubsigs.py` (new) and `AIL_CURRENT/tests.d/test_ail_stubsigs.txt` (new, one line:
  `test_ail_stubsigs`)
- the manifest files that `tools/update_manifest.py` writes

No compiler file imports `stubsigs` in this step, so the generated C and the compile time of every program are
unchanged by construction. Do not edit any other file under `AIL_CURRENT/`.

## Sub-steps

1. **Vendor (15 min).** `git clone --depth 1 https://github.com/python/typeshed` into a scratch directory outside the
   repository. Record in `third_party/typeshed/VERSION.md`: the URL, the full commit SHA, its date, the license
   (Apache-2.0; copy `LICENSE` unchanged), and the module list. The module list is the stdlib modules AIL already
   builds. Derive it, do not guess it: the modules named by `genlib.TABLE`, `stdlib3.MODULES`, the module docstrings of
   `stdlib4.py` / `stdlib5.py` / `stdtop.py`, the directories of `lab/stdlib/`, `AIL_CURRENT/stdlib/*.py`, plus `math`,
   `sys`, `os`, `os.path`, `time`, `string`, `operator`. Copy only `stdlib/<module>.pyi` (or `<pkg>/__init__.pyi`) for
   those, plus `builtins.pyi`. Write down the total bytes in `VERSION.md`; keep it under 1.5 MB. Commit, push, and open
   the PR against `integ`.
2. **Converter and table (30 min).** `tools/typeshed_convert.py` reads the vendored `.pyi` files with `ast` (they are
   valid Python) and writes `stubsigs_table.py`: one dict literal `SIGS = {...}` with sorted keys, deterministic bytes.
   It is a `.py` module, not JSON, because the wheel selects compiler files by suffix (`.py .h .c`, see
   `tools/update_manifest.py` `COMPILER_SUFFIXES`); check that before you choose otherwise. Rules:
   - key `module.function` (and `module.Class.method` only for classes the module defines; skip classes otherwise);
   - value `(ret, params, flags)`: `ret` is one of `int float bool str bytes None obj`; `params` is a tuple of
     `(name, kind, annotation_text)`, kind one of `pos kw star dstar`;
   - evaluate `if sys.version_info >= (3, N)` for Python 3.12 and `if sys.platform == ...` for `linux`, as CPython 3.12
     on Linux would see the stub; drop the other branches;
   - an `@overload` set gets `ret` only when every overload has the same `ret`, else `obj` and flag `overload`;
   - a TypeVar, a generic, an alias (`_T`, `SupportsFloat`), `Any`, `Literal[...]`, a union (`int | None`) or anything
     else not in the list gives `obj`. Never widen a guess: `obj` is the safe answer;
   - a stub `int` means AIL's checked int64 (the int64 default), not an unbounded int. Write that in the module
     docstring of `stubsigs.py`.
   Keep `stubsigs_table.py` under 200 KB. `stubsigs.py` exposes `lookup(qualname) -> (ret, params, flags) | None` and
   imports the table lazily, on the first call. Measure the cost of that first call with
   `python3 -X importtime -c "import stubsigs; stubsigs.lookup('math.gcd')"` (from `AIL_CURRENT/python/pkg-v12`) and
   write it in `RESULTS.md`. Target: under 10 ms. Commit and push.
3. **Counter (20 min).** `tools/typeshed_reach.py PATH...` walks every `.py` file, resolves `import m`, `import m as a`
   and `from m import f [as g]` (a name the program rebinds is not a stdlib call), and prints `total known scalar`, one
   line per module, and a `--list` mode that prints `file:line qualname ret`. Run it on `lab/census/programs/` and
   `lab/stdlib/`. Write the tables in `RESULTS.md` under "Before typeshed2", with the 20 most frequent call sites that are
   still unknown and why (not in the vendored list, a method of a returned object such as `re.compile(...).match`, a
   generic return). Commit and push.
4. **Test (15 min).** `test_ail_stubsigs.py`: running the converter again gives the committed `stubsigs_table.py` byte
   for byte; `lookup('math.gcd')[0] == 'int'`, `lookup('math.sqrt')[0] == 'float'`, `lookup('math.isclose')[0] ==
   'bool'`, `lookup('heapq.heappop')[0] == 'obj'` (generic), `lookup('no.such') is None`; `VERSION.md` names a 40-hex
   commit and `LICENSE` exists. Register the test (Appendix A rule 6) and run it. Commit, push, and wait for CI.

## Done-check

- `python3 AIL_CURRENT/test_ail_stubsigs.py` passes.
- `RESULTS.md` gives `total`, `known` and `scalar` for both corpora; `known / total >= 0.60` on `lab/census/programs/`.
- The first-lookup cost is in `RESULTS.md` and is under 10 ms.
- `git diff --stat origin/integ` shows only the files listed above. No other file under `AIL_CURRENT/` changes.
- The 20 shards pass.

## Stop rule

Stop and report if typeshed's `LICENSE` at the commit you clone is not Apache-2.0 (Apache-2.0 with some files under MIT
is fine; quote its first line), or if the
network clone fails (give the exact error). Stop when 80 minutes pass. Push what is done first.

## Appendix A: standing rules (from agent-brief-rules.md)

1. No regressions: a program that built and matched CPython before must still do so in the default build.
2. Probe ints beyond int64 wherever ints come from text or arithmetic; run probes in the default build and with
   `AIL_UNIFIED_FORCE=1`, compare both with `python3`.
3. Push early, open the PR against `integ`, wait for all 20 `shard` checks (`gh pr checks <n> -R J-KAMMA/ail-ci`, at most
   once every 10 minutes). Report only when all pass, or say which fail and why.
4. Branch from `integ` (or one unmerged PR at most).
5. Memory: wrap heavy runs in `ulimit -v 1500000`; `tools/par_check.py -j 2` at most; leave no background jobs.
6. New test module: `AIL_CURRENT/tests.d/<module>.txt` if the directory exists, else `ail_check.py` MODULES; `git add`,
   `tools/update_manifest.py`, then `tools/update_manifest.py --check`.
7. Never print credentials, run a broad pkill, merge PRs, change repository settings, cancel runs, tag, publish, or edit
   `.github/workflows`.
8. Never edit `AIL_CURRENT/ail_chatgpt.py`, `AIL_CURRENT/ail_syntax.py`, `AIL_CURRENT/python/pkg-v12/pyfunc.py`,
   `pyc.py`, `buildcache.py`, `pyboxed2.py`, or `packaging/ail_lang/cli.py`. Other lanes (pyreach, frontend) own them. Do
   not edit `DEVLOG.md` either: put your notes in the files this task names.

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT [--strict] [--debug-dir DIR]`. `DIR/program.c` is
  the generated C. `-o` must not exist yet. A fallback to the general path prints `note: ... built on the general path
  ...` on stderr.
- AIL is Python syntax plus optional annotations. Ints are int64, and overflow stops loudly (`--exact-int` /
  `AIL_EXACT_INT=1` is the opt-in for big ints).
- How stdlib calls are typed today: the typed path (`pyfunc.py`) lowers each supported module by hand-written passes
  (`stdlib3.py`, `stdlib4.py`, `stdlib5.py`, `stdtop.py`, `smalllib*.py`) and hand-written kind rules (`pyfunc._etype`,
  `_AIL_SYSINFO`, `_AIL_RAND`, `_AIL_CLOCK`). The general path (`pyboxed2.py`) reaches library code through
  `genlib.TABLE` preludes; its unboxing pass `unified.py` types a call only for a few builtins (`unified._etype`: `len`,
  `int`, `float`, `bool`, `round`, `abs`, `min`, `max`) and `random.Random` draws (`_DRAWS`); every `mod.f(...)` call is
  `OBJ` (boxed). `NAMES_library.json` is not in this tree (`genlib.py` docstring). That `OBJ` is where `typeshed2` plugs in.
- CPython 3.12 is the oracle.

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
