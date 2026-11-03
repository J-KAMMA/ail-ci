# job job-lsp1-11031803  started 2026-11-03T09:05:56Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Implemented on branch `job-lsp1-11031803`, commit `6954063`.

- Extended `ail lsp` with full-sync `textDocument/didChange`, buffer-based diagnostics through the existing `ail check` front end, inferred-type/signature hover, and a fix for strict blocker paths in nested directories.
- Added scripted clean/type-error/fallback LSP session tests, didChange tests, and hover tests in `AIL_CURRENT/test_ail_lsp.py`.
- Added `docs/LSP.md` with VS Code and Neovim setup.
- Updated DEVLOG and manifest pins; no generated C changes.

Verification on the final commit:
- `test_ail_lsp`: 20 passed
- `test_ail_safetynet`: 5 passed
- `test_ail_files`: 18 passed (1 skipped)
- `test_ail_corpus_findings3`: 2 passed
- Probes `/tmp/probes/lsp_{clean,type_error,fallback,hover}.py`: all matched CPython in both `g` and `d` builds.
[cost $0.0000, opencode tokens {"total": 4374417, "input": 108365, "output": 19611, "reasoning": 22953, "cache.write": 0, "cache.read": 4223488}]
    tool time: bash 8.7 min, write 0.0 min
        281s bash   python3 AIL_CURRENT/test_ail_files.py -q > /tmp/test_files.log 2>&1 & p1=$!; python3 AIL_CURRENT/test_ail_corp
        186s bash   python3 AIL_CURRENT/test_ail_lsp.py -q > /tmp/test_lsp.log 2>&1 & p1=$!; python3 AIL_CURRENT/test_ail_safetyne
          8s bash   mkdir -p /tmp/probes cat >/tmp/probes/lsp_clean.py <<'EOF' def main() -> None:     print(1 + 2)   main() EOF c
          6s bash   python3 - <<'EOF' from pathlib import Path p=Path('packaging/ail_lang/lsp.py') s=p.read_text() old='''        
          6s bash   python3 - <<'EOF' from pathlib import Path p=Path('AIL_CURRENT/test_ail_lsp.py') s=p.read_text() old='''    de
          6s bash   python3 - <<'EOF' from pathlib import Path p=Path('AIL_CURRENT/test_ail_lsp.py') s=p.read_text() s=s.replace('
          5s bash   for n in t1 t2 t3 t4; do f=/tmp/lsptypes/$n.py; echo ===$n; AIL_NO_CACHE=1 AIL_QUIET_FALLBACK=1 AIL_SDK_DIR=$P
          4s bash   python3 AIL_CURRENT/test_ail_lsp.py -v 2>&1 | tail -40

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change really does:** adds full/incremental `didChange`, checks buffer text by writing a sibling `.ail-lsp-*.py` temp file and running the existing `ail check`/strict front end, adds an independent AST-based hover type/signature inference, resolves strict blocker paths, and adds docs/tests. No compiler or generated-C change.

**Probes / results**
- `/tmp/rprobes/hover_semantics.py` via `bash ~/tools/cmp.sh ... $PWD`: g and d builds both match CPython (`float bool float float float`).
- `/tmp/rprobes/p_hover2.py`: clean file, `ail check` diagnostics `[]`; hover returns `int` for all five names below (expected `float bool float float float`).
- `/tmp/rprobes/p_change.py`: unicode/UTF-16 incremental edit, cross-line delete, empty full-sync text all work.
- `/tmp/rprobes/p_strict_cwd.py`: nested `strict/type_error.py` diagnostics land on the opened URI for cwd = project parent, `/tmp`, `/home/runner`, `/tmp/rprobes`.
- `/tmp/rprobes/p_import.py`: imported-module buffer diagnostic publishes on the right URI but its message names the deleted temp file.
- `/tmp/rprobes/p_readonly.py`: read-only directory, `didOpen` with broken buffer publishes nothing (timeout); base publishes `[]`.
- `--debug-dir` on a plain program: `program.c` byte-identical HEAD vs `/tmp/base`.
- `test_ail_lsp`: 20 passed; `test_ail_safetynet`: 5 passed; `update_manifest.py --check`: 0.

**Claims**
- didChange (full + ranges): verified.
- buffer diagnostics from the same front end: verified, except read-only dirs.
- inferred-type/signature hover: signatures verified; inferred values are **false** (wrong types, see defect 1).
- strict blocker path fix: verified.
- scripted 3-file session, docs, DEVLOG, manifest, no C changes: verified; the 3-file session checks diagnostics only (hover is a separate test).
- `test_ail_files` / `test_ail_corpus_findings3`: unverified (not re-run).

**Pre-existing:** checking `pkg/__init__.py` as an entry gives the same “relative import in the entry file” error on base; not caused by this change.

**Unverified:** speed (LSP is not hot code), `test_ail_files`, `test_ail_corpus_findings3`, other read-only/ACL layouts.

VERDICT: FIX
1. **Hover reports wrong types.** Probe `/tmp/rprobes/p_hover2.py`:
   ```python
   def main() -> None:
       a = 1 / 2
       b = not 1
       c = abs(-3.5)
       d = sum([1.5, 2.5])
       n = round(1.234, 2)
       print(a, b, c, d, n)
   main()
   ```
   `ail check` is clean and CPython/AIL both give `float bool float float float`; LSP hover gives `` `a`: `int` ``, `` `b`: `int` ``, `` `c`: `int` ``, `` `d`: `int` ``, `` `n`: `int` ``. Direct `type_hover` also gives `b"a b".split()` -> `list[str]` (should be `list[bytes]`), `range(3)` -> `list[int]` (should be `range`), shows a type for names inside strings/comments, and uses the last assignment for earlier lines (`p = 1; ...; p = "s"` -> `str` at both). Cause: `_value_type` at `packaging/ail_lang/lsp.py:252-330` and `_CALL_TYPES` at `:213` are a second, incorrect checker, not the compiler's types.
2. **Read-only project directories lose all diagnostics.** Probe `/tmp/rprobes/p_readonly.py`: directory chmod `0555`, `ro.py` on disk is clean, `didOpen` sends a syntax-error buffer. Expected a published syntax-error diagnostic; actual no `publishDiagnostics` at all (client times out). Base publishes `[]`. Cause: `analyse` unconditionally calls `tempfile.mkstemp(dir=path.parent)` at `lsp.py:531`; `PermissionError` is swallowed because `didOpen` has no request id.
3. **Buffer diagnostics leak the temp filename.** Probe `/tmp/rprobes/p_import.py`: opening `helper.py` with a syntax-error buffer publishes on `helper.py`, but the message is `AIL source /tmp/.../.ail-lsp-l916yoi3.py: invalid syntax (.ail-lsp-l916yoi3.py, line 2)`. Expected the message to name `helper.py`; `analyse` remaps only the problem path at `lsp.py:543`, not the message text.
[cost $0.0000, opencode tokens {"total": 1992248, "input": 41197, "output": 10122, "reasoning": 26561, "cache.write": 0, "cache.read": 1914368}]
    tool time: bash 5.7 min
        179s bash   date; python3 tools/update_manifest.py --check; echo "manifest check exit $?"; (cd AIL_CURRENT && timeout 300 
        120s bash   date; (cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_lsp test_ail_safetynet > /tmp/rev_tests.l
         11s bash   cat > /tmp/rprobes/p_readonly.py <<'PY' import sys, tempfile, time, os, stat from pathlib import Path sys.path
         10s bash   cat > /tmp/rprobes/p_hover.py <<'PY' import sys, tempfile, time from pathlib import Path sys.path.insert(0,"/t
          6s bash   date; cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 300 python3 test_ail_lsp.py -q 2>&1 | tail -6
          4s bash   cp /tmp/rprobes/p_hover2.py /tmp/rprobes/hover_semantics.py; sed -i '1,6d' /tmp/rprobes/hover_semantics.py 2>/
          2s bash   cd /tmp/rprobes; sed -i 's#^WT="/home/runner/work/_temp/w2"#WT=os.environ.get("WT","/home/runner/work/_temp/w2
          1s bash   cd /tmp/rprobes; sed 's#("cwd=unrelated", "/tmp")#("cwd=unrelated", "/home/runner"),("cwd=tmpchild", "/tmp/rpr

## worker report 1
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
(no final text)
[cost $0.0000, opencode tokens {}]
    tool time: 
(cut off after 60 minutes)

## review 1 failed to run: [cost $0.0000, opencode tokens {}]     tool time:  (cut off after 60 minutes) 

## review 1
[model opencode-go/deepseek-v4.1-flash]
(no final text)
[cost $0.0000, opencode tokens {}]
    tool time: 
(cut off after 60 minutes)

FINAL VERDICT: ERROR  2026-11-03T13:02:18Z
