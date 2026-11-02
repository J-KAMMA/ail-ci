Lane: frontend

**Owner decisions (2026-11-03):** AIL is one language, Python syntax plus optional annotations. The compare-lab `ail` column may use the converted annotated `typed.py` when its C is identical, and the plain `main.py` stays as its own row. The brace front end is removed before the 0.1 tag. AIL-only built-ins are spelled `from ail import ...`.

# onelang s1: the converter `tools/ail2py.py` (brace syntax -> annotated Python)

Time budget: 80 minutes. Commit and push after each sub-step.

**Number this moves:** all ten `lab/compare/src/*/main.ail` convert to Python files that `python3 -c "import ast;
ast.parse(open(F).read())"` accepts, and each converted file builds (`compile --strict --syntax python`) to a
`program.c` byte-identical to the one its `.ail` builds to. (A prototype already reaches 10/10; this step makes it a
tested tool with readable output and comments kept.)

Base: `origin/integ` of `https://github.com/J-KAMMA/ail-ci`. No compiler file changes in this step.

## Sub-steps

1. **Tool.** Create `tools/ail2py.py` (start from the prototype in Appendix C):
   - `python3 tools/ail2py.py SRC.ail [-o OUT.py]` writes the Python text (stdout when no `-o`).
   - Uses `ail_syntax.translate(src, module=<no fn main>, imports=imports, keep_contracts=False)` from `AIL_CURRENT`
     (`sys.path.insert(0, <repo>/AIL_CURRENT)`).
   - Rewrites the internal result markers: `__ail_checked_void__` -> `None`, `__ail_checked_flist__` -> `list[float]`,
     `__ail_checked_list[` -> `list[`, `__ail_checked_<X>__` -> `<X>`.
   - Writes `from <m> import *` first for each `use m` (the `imports` list), in order.
   - Entry files: replace the final `sys.exit(main())` with `if __name__ == "__main__":` / `    sys.exit(main())`.
   - Readable spacing: translate's `untokenize` gives `x =f (y )`. Re-render with `ast.unparse` per top-level node of
     `ast.parse(text)` (it keeps one statement per line), joining top-level `def`/`class` nodes with one blank line.
   - Comments: collect `#` comments from the brace source with `tokenize` (COMMENT tokens with their line numbers);
     pass `source_map={}` to `translate` (maps output line -> (source line, column)); after rendering, put each comment
     on its own line just before the first output statement whose source line is >= the comment's line, at that
     statement's indentation. A comment at the end of a code line goes on the line before that statement.
   - `ast.parse` the final text; exit 1 with the error if it fails.
   Commit, push, open the PR (draft) against `integ`.
2. **`--check`.** `python3 tools/ail2py.py SRC.ail --check [--flags "..."]`: converts into a temp dir, builds the original
   with `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC.ail -o T/a --debug-dir T/da <flags>` and the converted file
   with `... compile T/x.py -o T/p --syntax python --debug-dir T/dp <flags>`, and `cmp`s `T/da/program.c` with
   `T/dp/program.c`. Prints `identical`, `differ (<n> lines; first: <line>)`, `py-refused: <last stderr line>` or
   `both-fail`; exit 0 only for `identical`. Commit, push.
3. **Test module.** `AIL_CURRENT/test_ail_ail2py.py` (register: `AIL_CURRENT/tests.d/test_ail_ail2py.txt` if that
   directory exists, else the MODULES tuple of `ail_check.py`):
   - five small brace programs (struct + impl, `let` with `list[float]`, `-> void` function, `const`, try/except, a
     comment at line start and one at line end) converted. For each: the output parses, contains no `__ail_`, and keeps
     both comments. For two of the five: `--check` prints `identical`. For the other three: the converted file run by
     `python3` prints the same stdout and exit code as the AOT binary of the `.ail`.
   - `git add`, `python3 tools/update_manifest.py`, then `python3 tools/update_manifest.py --check`. Commit, push.
4. **Done-check run** (Appendix D). Paste its 10 lines into the PR description. Commit any fix, push.

## Done-check

`bash` loop of Appendix D prints `identical` for all ten tasks; `python3 AIL_CURRENT/test_ail_ail2py.py` passes; all 20
`shard` checks pass on the PR head.

## Stop rule

Stop and report (push what is green) if: any of the ten is not `identical` after sub-step 1 and the cause is not in
`tools/ail2py.py` itself (the prototype gave 10/10, so a difference means the rendering changed meaning); `ast.unparse`
re-rendering changes the C of any task (then keep translate's own text and only fix spacing with a token pass); a
compiler file would need a change; or 80 minutes pass. Do not touch `.github/workflows`.

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

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT [--syntax python] [--strict] [--debug-dir DIR]`;
  `DIR/program.c` is the generated C. `--strict` = typed path or refuse.
- Brace front end: `AIL_CURRENT/ail_syntax.py` `detect()` (about line 206) picks brace syntax when the first two tokens
  are a NAME in `fn const use struct impl` and another NAME; `translate()` (about line 285) turns brace text into
  annotated Python text, one statement per line, adding `import sys` / `sys.exit(main())`, `class S:` +
  `def __init__(self, f: T, ...)` for a struct, `-> __ail_checked_<R>__` for `-> R`, `return 0` at the end of `main`.
  `keep_contracts=True` keeps `requires`/`ensures` as `__ail_requires__(c)` calls (used by `ail_sexpr.py`); use
  `False` here so they become the `assert` lines.
- `python_surface()` (about line 4101) maps Python spellings onto the compiler's built-ins (`-> str` checked,
  `heapq.heappush`, `sys.stdin.buffer.read()` -> `read_stdin_bytes`, `@dataclass` -> `__init__`).
- `use m` resolves `AIL_CURRENT/language_examples/m.ail`; in Python, `from m import *` is merged by
  `AIL_CURRENT/ail_modules.py` (`merge_program`), which renames module names `m.f` -> `m__f` in the C.
- compare-lab: `lab/compare/src/<task>/main.ail` (brace), `main.py` (plain CPython program); tasks: berth_sim
  chain_relax echo_pack ledger_bin rail_transfer scar_life tally_lang term_rank ticket_audit tree_fold.

## Appendix C: prototype converter (measured: 10/10 byte-identical C on 2026-11-03)

```python
import sys, re
sys.path.insert(0, 'AIL_CURRENT')
import ail_syntax
def convert(src, entry=True):
    imports = []
    text = ail_syntax.translate(src, module=not entry, imports=imports, keep_contracts=True)
    text = re.sub(r'__ail_checked_void__', 'None', text)
    text = re.sub(r'__ail_checked_flist__', 'list[float]', text)
    text = re.sub(r'__ail_checked_(\w+?)__', r'\1', text)
    text = re.sub(r'__ail_checked_list\[', 'list[', text)
    head = ''.join(f'from {m} import *\n' for m in imports)
    if entry:
        text = text.replace('\nsys.exit(main())\n', '\nif __name__ == "__main__":\n    sys.exit(main())\n')
    return head + text
```

(The prototype used `keep_contracts=True`; no compare-lab file has contracts, so both settings give the same text there.)

## Appendix D: done-check loop

```bash
cd <repo>; ulimit -v 1500000
for t in berth_sim chain_relax echo_pack ledger_bin rail_transfer scar_life tally_lang term_rank ticket_audit tree_fold; do
  printf '%s ' $t; python3 -B tools/ail2py.py lab/compare/src/$t/main.ail --check --flags "--strict"
done
```

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
