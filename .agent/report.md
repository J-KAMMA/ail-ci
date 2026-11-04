# job job-lsp1c-11041016  started 2026-11-04T01:17:00Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Applied lsp1b work onto `job-lsp1c-11041016` (commits `0daf6c1f`, `1312025b`, `a1f750b9` as a no-op, `443de740`, `4f8b03ef`, `c15d95b4`; skipped `dff957af`). Compiler/reference files remain exactly as on the base export; only `packaging/ail_lang/lsp.py`, `AIL_CURRENT/test_ail_lsp.py`, `docs/LSP.md`, `DEVLOG.md`, `AIL_CURRENT/manifest.d/66.txt` changed.

Measurements:
- Review probe: all five names (`a,b,c,d,n`) hover `null`; wrong hovers 5 → 0.
- `b"a b".split()`, `range(3)`, strings/comments, attributes, keyword labels: all `null`.
- Read-only `0555` directory: syntax-error buffer publishes a diagnostic.
- Diagnostic message: no `.ail-lsp-*` temp name leaks.

Verification:
- `test_ail_lsp`: 32 passed.
- `test_ail_safetynet`: 5 passed (under `ulimit -v 1500000`, only pre-existing `S4_generators_gc` fails due the VM cap; no compiler files touched).
- `test_ail_files`: passed. `test_ail_corpus_findings3`: passed.
- `tools/update_manifest.py --check`: clean.
- Probes `/tmp/probes/review_probe.py`, `hover_literals.py`, `hover_boundaries.py`: all matched CPython on default and `AIL_UNIFIED_FORCE=1` builds.

No push (forbidden by job rules); 20-shard CI not run locally, per the rule that the full suite runs on CI after merge.
[cost $0.0000, opencode tokens {"total": 2025486, "input": 58121, "output": 6165, "reasoning": 13424, "cache.write": 0, "cache.read": 1947776}]
    tool time: bash 10.1 min
        356s bash   ulimit -v 1500000; python3 tools/par_check.py -j 2 test_ail_safetynet test_ail_files test_ail_corpus_findings3
        178s bash   python3 AIL_CURRENT/test_ail_safetynet.py 2>&1 | tail -30
         40s bash   python3 tools/par_check.py --help 2>&1 | head -40; echo ===; python3 AIL_CURRENT/test_ail_lsp.py 2>&1 | tail -
         14s bash   mkdir -p /tmp/probes && cat > /tmp/probes/review_probe.py <<'PY' def main() -> None:     a = 1 / 2     b = not
          9s bash   git fetch origin job-lsp1b-11040505 job-lsp1-11031803 integ 2>&1 | tail -20
          3s bash   cat > /tmp/probes/hover_boundaries.py <<'PY' class Box:     def __init__(self) -> None:         self.v = 2  de
          3s bash   sed -i 's/(1)\.real/(1.5).real/' /tmp/probes/hover_boundaries.py; bash .agent/cmp.sh /tmp/probes/hover_boundar
          0s bash   python3 tools/update_manifest.py --check 2>&1 | tail -30; echo "exit=${PIPESTATUS[0]}"

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change really does:** applies the lsp1/lsp1b work: full-sync `didChange`, conservative AST hover (annotation / literal type / signature), buffer checking through a temp sibling file with a read-only temp-dir fallback plus `AIL_PATH`, diagnostic path remapping, docs and tests. No compiler/runtime files change, so generated C is unchanged. This matches the report except that `docs/LSP.md` is added (not edited) and the `/tmp/probes/*.py` are compile programs, not hover probes.

**Probes run**
- Review probe: `a,b,c,d,n` all hover `null`; diagnostics clean. Verified.
- Literal types `i,f,s,b,t,n` correct; values from a list item, dict value, attribute, argument and name are `null`; mixed kinds and augmented assignment are `null`; strings, comments and f-string expressions are `null`; a name after a non-BMP character uses the UTF-16 position correctly.
- `b"a b".split()`, `range(3)`, attribute `obj.x`, keyword label `f(x=2)`: `null`. Verified.
- Read-only `0555`: syntax-error buffer publishes an Error; no `.ail-lsp-*`/temp-dir name leaks; imports resolve; general-path import is a Warning. Verified.
- Diagnostic remap: real path and base name shown; no temp name. Verified.
- A program not using the feature matches CPython on HEAD and base; only the five allowed files changed.

**Claims:** applied work / allowed files verified; review probe 5→0 verified; `test_ail_lsp` 32/32 verified; `test_ail_safetynet` 5/5 without the VM cap (under `ulimit -v 1500000`, S4_generators_gc fails identically on base); `test_ail_files` and `test_ail_corpus_findings3` pass; manifest check clean. The report's `/tmp/probes` claim verifies compile behaviour only, not hover.

**Defects (introduced by the new hover; base returns `null` for all three)**

1. Hover treats a class body as an enclosing scope for methods. Probe `/tmp/rprobes/lsp_scope2.py`:
   ```python
   x = "s"
   class C:
       x = 1
       def f(self):
           print(x)
   C().f()
   ```
   CPython prints `s`. Hover on `x` in `print(x)` gives `` `x`: `int` `` (the class attribute); expected `` `x`: `str` `` (module literal) or `null`. Same probe with a global `def g()` and a method `def g(self)`: hover on `g` inside the other method shows the method signature `def g(self)`; expected the global `def g()` or `null`.
2. Lambda parameters are not a scope. Probe `/tmp/rprobes/lsp_scope4.py`:
   ```python
   def f():
       x = "s"
       g = lambda x: x
       print(g(2), x)
   f()
   ```
   Hover on the lambda parameter `x` and on the lambda body `x` gives `` `x`: `str` `` (the outer literal); expected `null`, because the lambda parameter shadows it and has no annotation.
3. `global` declarations are ignored. Probe `/tmp/rprobes/lsp_scope5.py`:
   ```python
   x = "s"
   def f(cond: bool) -> None:
       global x
       if cond:
           x = 1
       print(x)
   f(False)
   ```
   CPython prints `s`. Hover on `x` in `print(x)` gives `` `x`: `int` ``; expected `null` (the global has both a `str` and an `int` literal assignment).

These violate the task's rule that a wrong type is worse than no type; the added tests do not cover class, lambda or `global` scoping.

**Pre-existing (not blocking):** under `ulimit -v 1500000`, `test_ail_safetynet` S4_generators_gc fails identically on base `work`. A read-only directory with `ail.toml strict = true` yields a Warning rather than an Error because `project.find()` runs on the temp-dir probe; base behaves the same for a non-existent buffer file, so this is not introduced here (but `docs/LSP.md` overstates that the project file keeps working in that case).

**Unverified:** the 20-shard CI (not pushed); the worker's `/tmp/probes` do not exercise hover. Negative literals (`i = -7`, `f = -0.0`) hover `null`; safe, but not the `int`/`float` the literal rule might imply.

VERDICT: FIX
[cost $0.0000, opencode tokens {"total": 1407664, "input": 40622, "output": 10776, "reasoning": 43882, "cache.write": 0, "cache.read": 1312384}]
    tool time: bash 16.3 min
        371s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && ulimit -v 1500000; timeout 600 python3 ../tools/par_check.py
        183s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 500 python3 AIL_CURRENT/test_ail_safetynet.py 2>&1 | tail -8; da
        156s bash   ulimit -v 1500000; cd AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_lsp test_ail_safe
        153s bash   cd /tmp/base && ulimit -v 1500000; timeout 400 python3 AIL_CURRENT/test_ail_safetynet.py 2>&1 | tail -20
         45s bash   cd /home/runner/work/ail-ci/ail-ci && python3 AIL_CURRENT/test_ail_lsp.py 2>&1 | tail -6; echo ===; ls -la /tm
         17s bash   cat > /tmp/rprobes/lsp_ro.py <<'PY' import os, sys, tempfile, stat from pathlib import Path REPO = Path("/home
         14s bash   cd /home/runner/work/ail-ci/ail-ci; for f in /tmp/probes/review_probe.py /tmp/probes/hover_literals.py /tmp/pr
          7s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check 2>&1 | tail -5; echo "manifest 

## worker report 1
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Mostly passing; three failures are my probe's own indexing. Let me correct the probe and add more boundary cases (del, reassignment, nested closures, class-in-function).
[commandcode stop=permission_denied turns=7 out_tokens=12423]

## review 1 failed to run: [model commandcode/deepseek-v4.1-flash] My probe positioned most cursors at the start of the needle, not on the identifier. Let me correct that and re-run. [commandcode stop=permission_denied turns=11 out_tokens=14027] 

## review 1
[model commandcode/deepseek-v4.1-flash]
# Review: lsp1b (hover / read-only dirs / message remap)

**What the change does:** in `packaging/ail_lang/lsp.py` it adds full-sync `didChange`, a conservative `type_hover` (signature / annotation / all-literal-one-kind, else null), a read-only fallback that probes the buffer in a `mkdtemp` dir with `path.parent` on `AIL_PATH`, and path/base-name remapping of diagnostic messages; plus tests, docs and DEVLOG. That matches the DEVLOG. The worker's own report is truncated ("Mostly passing; three failures are my probe's own indexing…") and contains no probe list or numbers, so I treated the DEVLOG as the claim set.

**Probes** (`/tmp/rprobes/`, run on HEAD and on `/tmp/base` = `work`):
- `rev_hover.py` (44 direct `type_hover` cases): 5 review names → null; `b"a b".split()`, `range(3)` → null; strings/comments/attribute/keyword-label → null; int/float/str/bytes/bool/None → correct; same-type reassignment → type; mixed/alias/argument/list-item/dict-value/attribute/`for`-target/augassign/tuple-unpack/`-1` → null; annotation and signature correct; global/nonlocal/class/comprehension/lambda scoping correct; UTF-16 positions correct (`raw char` pos → null, `unit` pos → `int`). No wrong type found.
- `rev_server.py` (real server): writable + read-only `didOpen` publish clean messages (`helper.py`, no `.ail-lsp-`), no temp leftovers; read-only new and existing files both publish; `didChange` full and range (including after an astral char) work and leave the file untouched; imported-module diagnostics publish on the import's own URI. `R5` (read-only `module_path` import) fails **identically on base and HEAD** — `ail check -I lib` ignores `-I`, so pre-existing.
- `cmp.sh` on `p_sanity.py`, `p_imports.py`, `p_slice.py`: both builds match CPython, exit 0. `--debug-dir` generated `program.c` identical base vs HEAD (1,171,220 bytes). Diff touches no compiler/runtime file, so no speed impact (icount not applicable).

**Tests on HEAD:** `test_ail_lsp` passed (65.9 s). `test_ail_safetynet` failed `S4_generators_gc` under `-j 2`; standalone that case matches CPython exactly on HEAD **and** on base — a concurrency flake, not caused by the change. `tools/update_manifest.py --check` clean. `test_ail_files`/`test_ail_corpus_findings3` and the 20 shards were not run (Unverified).

**Defect (caused by the change):**
1. **A read-only project loses `strict`, so an Error becomes a Warning.** The fallback hand-checks a probe file in `mkdtemp`, so `project.find(probe.parent)` cannot see the project's `ail.toml`; `found_strict` becomes False. Base checked the on-disk file and found the project.
   Probe (`/tmp/rprobes/rev_server.py` R3): directory at `0555` containing `ail.toml` (`entry = "blocker.py"`, `strict = true`) and, on disk, `blocker.py` = `def find(d: dict[int, int], k: int) -> int | None: …`; `didOpen` of that file.
   Expected (base, and `docs/LSP.md`): severity **1** (Error), message `int | None: only a class type can be None here …`.
   Actual HEAD: severity **2**, `runs on the slow general path because int | None: …`.
   (For a *new* file in a read-only dir this was already broken on base; the regression is the existing-file/`didChange` case.)

**Minor, non-blocking:** `_annotation`'s docstring says "exactly as the source writes it", but it is `ast.unparse`: `x: dict [ int , int ]` hovers as `dict[int, int]`. `-1`, `x, y = 1, 2` and `x = 1 if c else 2` show no type (conservative; the rule arguably expects `int`).

**Pre-existing:** R5 `module_path` import (`ail check` ignores `-I`); `S4_generators_gc` flake under parallel load.

**Unverified:** the 20 shards, `test_ail_files`, `test_ail_corpus_findings3`; the VS Code/Neovim snippets in `docs/LSP.md`.

VERDICT: FIX
1. Read-only directories drop the project's `strict` setting: with `ail.toml` `strict = true` and a typed-path blocker in a `0555` directory, `didOpen` of the on-disk file publishes severity 2 (`runs on the slow general path because int | None…`) where base and the docs give severity 1 (`int | None: only a class type can be None here …`). Cause: `Diagnoser.diagnose` runs `project.find` on the `mkdtemp` probe's parent instead of the opened file's parent.
[commandcode stop=end_turn turns=41 out_tokens=53013]

FINAL VERDICT: FIX  2026-11-04T04:26:20Z
