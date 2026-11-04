**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model commandcode/deepseek-v4.1-flash]
I've completed the probe and test runs. Here is my review.

## Review: toml1 fix round

**What the change really does:** In the bundled `stdlib/tomllib`, it replaces the old `declared`/`implicit` sets with bitmask flag maps (`direct`/`recursive`, `pending`) to reproduce CPython's `FROZEN`/`EXPLICIT_NEST` checks, fixes base-prefixed number scanning and the empty-datetime fraction, adds `bytearray` to `load()`, makes `parse_float` keyword-only, and makes the `parse_float` default an identity-only function object. No compiler/runtime files are touched.

**Verified claims**
- All five review defects: `p1_frozen`, `p2_namespace`, `p3_scalars`, `p4_datetime`, `p12_frozen_headers` now match CPython in both builds (`g` and `d`), as do `p5_load`, `p7_inline`, `p8_parsefloat`, `p9_tables`, `p10_dotted`, `p11_valid`, `p13_badpf`, `pf_sentinel`, `pf_func`.
- `p6_posargs` (`loads(doc, 0)`) is a named compile-time refusal (`not in the subset: ... loads() called with too many positional arguments`) in both builds — acceptable.
- `load`/`loads`/sentinel paths through arguments, list items, attributes and dict values (`q_pfpaths`), bytearray readers and buffer reuse (`q_load2`) match CPython.
- `test_ail_std_tomllib` OK (`351.0s`); `test_ail_safetynet` fails only `S4_generators_gc` (pre-existing, verified on base by the prior review). `update_manifest.py --check` rc=0.
- Unrelated program: hello-world `--debug-dir/program.c` is byte-identical HEAD vs `/tmp/base`.
- Claim "string sentinel was silently treated as float" is true (`b8b0009` used `== "DEFAULT"`); `q_load` l6/l7 now match CPython.
- Claim "no user-supplied value can match it" is **overstated**: `tomllib._parser._PARSE_FLOAT_DEFAULT` is reachable (`q_sentinel`: CPython AttributeError; AIL `ok {'x': 1.5}`). Not a defect for portable programs, but the claim is false.

**Defect (caused by this change; base matches CPython)**
1. Joined key paths use `\0` as separator, and the new full-path recursive `FROZEN` flag aliases a distinct key containing an escaped NUL. `q_nul2.py`:
```python
import tomllib
for s in ['a.b = {}\n["a\\u0000b"]\nc = 2\n', 'a.b = {}\n"a\\u0000b".c = 1\n']:
    try: print("ok", tomllib.loads(s))
    except Exception as e: print(type(e).__name__, e)
```
Expected (CPython and `/tmp/base`): `ok {'a': {'b': {}}, 'a\x00b': {'c': 2}}` / `ok {'a': {'b': {}}, 'a\x00b': {'c': 1}}`.
Actual HEAD (both builds): `TOMLDecodeError Cannot declare ('a\x00b',) twice (at line 2, column 12)` / `TOMLDecodeError Cannot mutate immutable namespace ('a\x00b',) (at line 2, column 17)`. (`q_nul` k1/k3 are the same family but pre-existing; k2 is new.)

**Pre-existing (identical on `/tmp/base`, not blocking)**
- `q_nul` k1/k3: direct-flag NUL alias already wrong on base.
- `q_num` n1–n3: datetime/time printing (`<_AilDT object>`, time as source text) — known compiler limit.
- `q_load` l3 (custom `.decode()` reader accepted by CPython, rejected), l12 (`loads(s=...)` accepted, CPython rejects), l11 `parse_float=float` is a named refusal.
- `q_sentinel` and `S4_generators_gc`.

**Unverified**
- Wider suite, shards/CI, and speed: not applicable — the diff is stdlib-only, no benchmark program or compiler/runtime code is edited, and unrelated generated C is identical.

VERDICT: FIX
1. NUL-in-key aliasing regression. Probe `/tmp/rprobes/q_nul2.py` (`a.b = {}\n["a\u0000b"]\nc = 2` and `a.b = {}\n"a\u0000b".c = 1`): expected `ok {'a': {'b': {}}, 'a\x00b': {'c': 2}}` and `ok {'a': {'b': {}}, 'a\x00b': {'c': 1}}`; actual `TOMLDecodeError Cannot declare ('a\x00b',) twice` and `TOMLDecodeError Cannot mutate immutable namespace ('a\x00b',)`.
[commandcode stop=end_turn turns=32 out_tokens=40687]


--- ORIGINAL TASK ---
Lane: toml

# toml1: `import tomllib` as a bundled AIL package (`AIL_CURRENT/stdlib/tomllib/`), so CLI tools can read TOML config

Time budget: 80 minutes. Commit and push after each sub-step.

**Number this moves:** programs in `lab/stdlib/tomllib/` that build in the default mode and print what CPython prints,
with the same exit status. On `integ` today it is 0/12. A probe on 2026-11-04 copied CPython 3.12's `tomllib`
package next to a program and built it; the first refusal was
`not in the subset: a required keyword-only parameter recursive in def set (this cut requires every keyword-only
parameter to have a default)`, followed by notes about `None` stored in a container and a tuple element type. The
target is at least 8/12. Reading a config file is what the roadmap's P4 niche (small CLI and data tools) needs most
after argument parsing (`getopt1`).

Base: `origin/integ`. Files you may create or edit, and no others:
- `AIL_CURRENT/stdlib/tomllib/__init__.py`, `_parser.py`, `_re.py`, `_types.py` (new)
- `lab/stdlib/tomllib/*.py` (12 programs) and `lab/stdlib/tomllib/RESULTS.md` (new)
- `AIL_CURRENT/test_ail_std_tomllib.py` (new) and `AIL_CURRENT/tests.d/test_ail_std_tomllib.txt` (new, one line:
  `test_ail_std_tomllib`)
- the manifest files that `tools/update_manifest.py` writes

## Sub-steps

1. **Programs and baseline (15 min).** Write 12 programs in `lab/stdlib/tomllib/`, each 15-40 lines of ordinary
   Python 3.12. Each passes a TOML string written in the program to `tomllib.loads` (no files needed), then prints the
   result with `print()` and selected fields. Together they cover: key/value pairs with every scalar type (basic and
   literal strings, multi-line strings with escapes and line-ending backslashes, ints in decimal, hex `0x`, octal
   `0o`, binary `0b` and with `_`, floats with exponent, `inf`, `nan`, booleans); tables, dotted keys, inline tables,
   arrays of tables `[[x]]`, nested arrays; offset date-times, local date-times, dates and times (they print as
   `datetime` objects); `parse_float=decimal.Decimal` only if `decimal` builds (else use `parse_float=float` and say
   so); a CLI config loader that merges defaults with the parsed table; `tomllib.load` from `io.BytesIO`; errors caught
   as `except tomllib.TOMLDecodeError as e:` and printed with `str(e)` (a duplicate key, an unclosed string, an invalid
   value); and an int beyond int64 (`x = 99999999999999999999`): print what CPython prints, or let the program stop
   loudly. Build each with the default command; record typed, general or refused, with the first refusal line, in
   `RESULTS.md` under "Before (integ <short sha>)". Commit, push, and open the PR against `integ`.
2. **The package (30 min).** Copy CPython 3.12's `Lib/tomllib/` files (find them with
   `python3 -c "import tomllib, os; print(os.path.dirname(tomllib.__file__))"`) into `AIL_CURRENT/stdlib/tomllib/`.
   Then make them build, one refusal at a time, rewriting only what the compiler refuses and keeping the behaviour:
   for example give each required keyword-only parameter (`recursive` in `Flags.set`, and others) a default and pass
   it at every call; replace `None` stored in a container by a sentinel object; annotate tuple elements. Keep a list
   of every rewrite, with the refusal text it answers, in the docstring of `__init__.py`. Every error message must
   stay CPython's (the `TOMLDecodeError` texts include the line and column). Commit and push after each 3 rewrites.
3. **Make the programs pass (20 min).** Build all 12 again in the default build and with `AIL_UNIFIED_FORCE=1`. Fix the
   package, never the programs, until at least 8 build and match. A refusal that needs a compiler file goes into
   `RESULTS.md` as a follow-up with the exact refusal text, ranked by how many programs it blocks. Record the build
   time of one program (median of 3, `AIL_NO_CACHE=1`) against a hello-world build. Commit and push.
4. **Test (15 min).** Write `AIL_CURRENT/test_ail_std_tomllib.py`, copying the structure of
   `AIL_CURRENT/test_ail_std_shlex.py`: it builds every passing program and compares stdout and the exit status with
   `python3`, in both builds, and skips when there is no C compiler. Register it (Appendix A rule 6) and run
   `python3 tools/par_check.py -j 2 test_ail_std_tomllib`. Fill `RESULTS.md` under "After". Commit, push, and wait for
   CI.

## Done-check

- `python3 AIL_CURRENT/test_ail_std_tomllib.py` passes.
- At least 8 of the 12 programs build and match CPython in both builds.
- `RESULTS.md` has the before/after table, the build-time row, and the ranked follow-ups.
- The 20 shards pass.
- `git diff --stat origin/integ` shows only the files listed above.

## Stop rule

Stop and report if a bundled package directory is not picked up by `import tomllib`; give the exact message. Also
stop if fewer than 5 programs can pass without editing a compiler file: push the package as far as it builds and
the ranked list of blocking refusals (that list is the deliverable then). Stop when 80 minutes pass. Push what is
done first.

## Appendix A: standing rules (Follow C:\Users\bluec\ail-work\agent-brief-rules.md)

1. No regressions: a program that built and matched CPython before must still do so in the default build. A loud
   stop is allowed only where the value cannot be computed.
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
   `pyc.py`, `buildcache.py`, `pyboxed2.py`, `cruntime.py`, or `packaging/ail_lang/cli.py`. Other lanes own them. Do not
   edit `DEVLOG.md` either: put your notes in the files this task names. Edit only the files this task names, plus the
   manifest files that `tools/update_manifest.py` writes.

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT [--strict] [--debug-dir DIR]`. `DIR/program.c` is
  the generated C. `--strict` means the typed path or a refusal. `-o` must not exist yet. A fallback to the general
  path prints `note: ... built on the general path ...` on stderr.
- AIL is Python syntax plus optional annotations. Ints are int64, and overflow stops loudly.
- Modules in `AIL_CURRENT/stdlib/` are standard modules shipped as AIL source; a package is a directory with an
  `__init__.py`. `AIL_CURRENT/ail_modules.py` (`BUNDLED_DIR`, line ~85) searches them after the program's own directory
  and `AIL_PATH`. Examples: `AIL_CURRENT/stdlib/shlex.py` and its test `AIL_CURRENT/test_ail_std_shlex.py`.
- CPython 3.12 is the oracle: compare stdout and the exit status, and stderr where a task says so.

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
