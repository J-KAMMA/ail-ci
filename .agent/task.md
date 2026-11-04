Lane: smoke

# smoke1: install smoke test of the `ailc` wheel on clean Linux containers (no workflow edits)

Time budget: 80 minutes. Commit and push after each sub-step.

**Number this moves:** the clean Linux images on which the wheel built from this checkout installs into a fresh venv
and the installed `ail` passes four checks:
- `ail --version`;
- `ail doctor --check`;
- `ail run` of hello world;
- a typed `fib`, which must print what `python3` prints.

Not measured today: CI checks only one image per OS (`.github/workflows/platforms.yml`, job `wheel`). Target: a
pass/fail table over **8 images**, with the first error line for each failure. One more check: on an image with no C
compiler, `ail doctor` must name the missing compiler and exit non-zero. This is roadmap P4, the install smoke test.
macOS and Windows are out of scope: CI already installs the wheel there.

Base: `origin/integ`. Files you may create or edit, and no others:
- `tools/install_smoke.py` (new)
- `packaging/SMOKE.md` (new)

Do not edit `tools/wheel_check.py`, `packaging/ail_wheel_backend.py`, `packaging/ail_lang/*`, `pyproject.toml` or any
workflow. If an image fails because of a packaging bug, record it in `SMOKE.md` with the exact error and the
smallest reproducer. Do not fix it here. This job adds no test module: the gate has no docker.

## The images

Pin each by its exact tag:
- `python:3.10-slim-bookworm`, `python:3.11-slim-bookworm`, `python:3.12-slim-bookworm`, `python:3.13-slim-bookworm`:
  install `gcc libc6-dev` with apt first;
- `debian:12`: apt `python3 python3-venv gcc libc6-dev`;
- `ubuntu:24.04`: the same packages;
- `fedora:41`: dnf `python3 gcc`;
- `alpine:3.20`: apk `python3 py3-pip gcc musl-dev`. This is musl libc; a failure here is a finding, not a skip.
The no-compiler check uses `python:3.12-slim-bookworm` with nothing installed.

## Sub-steps

1. **The script, one image (20 min).** Read `tools/wheel_check.py` for these: how it builds the wheel
   (`pip wheel . --no-deps --no-build-isolation`), its hello and typed-fib programs, and how it runs
   `test_ail_tutorial.py` against the installed command. Do not import its private functions: copy the two small
   program texts. Write `tools/install_smoke.py [--images A,B] [--engine docker|podman] [--keep]`. It builds the
   wheel once on the host into a temporary directory. For each image it runs
   `docker run --rm --memory=1500m -v WHEELDIR:/w:ro -v CHECKS:/c:ro IMAGE sh -c '...'`, which does the following:
   installs the packages, makes a venv in `/tmp/v`, runs `pip install /w/*.whl` with `--no-index`, then runs the
   four checks. For the typed fib it compares the output with the image's own `python3`. Each check prints one line,
   `CHECK name PASS|FAIL first-error-line`. The script parses those lines and prints a table. The exit status is 0
   only when every check passes. Get one image, `python:3.12-slim-bookworm`, fully passing. Commit, push, and open
   the PR against `integ`.
2. **All images (20 min).** Run all 8 images. Use a 10-minute timeout per image, and pulls are allowed. Add
   `docs/tutorial.md` as a fifth check. Mount the checkout read-only at `/src`, and run
   `/tmp/v/bin/python /src/AIL_CURRENT/test_ail_tutorial.py` the way `wheel_check.py` points it at the installed
   command. Find the variable or argument it uses there. Record each image's result. Commit and push.
3. **No-compiler check and probes (15 min).** Add the `nocc` case. Use `python:3.12-slim-bookworm` with no gcc.
   `ail doctor --check` must exit non-zero, and its output must name the missing C compiler. `ail run hello.py`
   must fail with a message, not a traceback. Record what it prints. Add one probe to the typed check on every
   image: `print(2**62 + 2**62 - 1)`, which is the int64 edge, must equal CPython's output. Commit and push.
4. **Report (15 min).** Write `packaging/SMOKE.md`: the command to run the script, the date, the commit, and the
   table (image, Python version, libc, the 5 checks, wall seconds). Then the findings, each with its exact error
   line. Commit, push, and wait for CI (the shards still run on the PR).

## Done-check

- `python3 tools/install_smoke.py` runs on the runner and prints the table for 8 images plus `nocc`.
- `SMOKE.md` has the table and the findings.
- `git diff --stat origin/integ` lists only the two new files.
- The 20 shards pass.

## Stop rule

Stop and report if neither docker nor podman can run a container on the runner within 10 minutes of trying; say what
you tried. Stop if the wheel does not build on the host; give the error. Stop when 80 minutes pass. Push what is
done first. Remove every container and image you pulled before you report (`docker image rm` of the 9 tags only;
never a broad prune).

## Appendix A: standing rules (from agent-brief-rules.md)

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
   `pyc.py`, `buildcache.py`, `pyboxed2.py`, or `packaging/ail_lang/cli.py`. Other lanes own them. Do not edit
   `DEVLOG.md` either: put your notes in the files this task names. Edit only the files this task names, plus the
   manifest files that `tools/update_manifest.py` writes.

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT [--strict] [--debug-dir DIR]`. `DIR/program.c` is
  the generated C. `--strict` means the typed path or a refusal. `-o` must not exist yet. A fallback to the general
  path prints `note: ... built on the general path ...` on stderr.
- AIL is Python syntax plus optional annotations. Ints are int64, and overflow stops loudly.
- Modules in `AIL_CURRENT/stdlib/*.py` are standard modules shipped as AIL source. `AIL_CURRENT/ail_modules.py`
  (`BUNDLED_DIR`, line ~85) searches them after the program's own directory and `AIL_PATH`. Examples:
  `AIL_CURRENT/stdlib/shlex.py` and its test `AIL_CURRENT/test_ail_std_shlex.py`.
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
