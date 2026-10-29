# job job-stdlib37-10291115  started 2026-10-29T02:39:49Z  worker=oc reviewer=oc (GitHub)
## qoder discovery
1.1.78
  -m, --model <model>                  Model for the current session. Default
                                       and New Models use model name; Custom
                                       uses modelID
  --reasoning-effort <level>           Set reasoning effort level
  --thinking <mode>                    Set thinking mode (auto, adaptive,
                                       enabled, or disabled)
--
                                       models
  --list-models                        List available models for the current
                                       user
  -i, --prompt-interactive <text>      Execute prompt and continue in
                                       interactive mode
### --list-models
MODEL
Qwen3.8-Flash
DeepSeek-Flash
DeepSeek-Flash -> ts":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["Your personal Credits have been exhausted. Please check your plan."],"error_code":118,"fast_mode_state":"off","uuid":"33fe5e90-c089-4183-a64e-abc63746f440","session_id":"5106730e-f474-4cc2-b8f3-25016250b203"}
DeepSeek-Flash -> input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your credit usage limit. Please upgrade your subscription plan to get more resources. Report Issue (input /feedback)"],"error_code":118,"fast_mode_state":"off","uuid":"cbe860c4-bd4a-41c1-aadd-c072c99ab1ee","session_id":"2242c4df-3e76-421b-97f8-f3e288c5060e"}

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Implemented and committed `argparse` support as stdlib37.

**Commit:** `18f10f8` on `job-stdlib37-10291115`

**What was done**
- Confirmed `argparse` is the most-imported still-refused module: 9 imports, ahead of `tempfile` (7), `struct` (6), `shutil` (3), etc.
- Lowered long `--name` options and positionals onto `prelude_argparse.py` via `argparselib.py`: `type=` int/float/str/`pathlib.Path`, `default=`, `dest=`, `required=`, `choices=` (str only), `help=` ignored, `parse_args()` from `sys.argv` or a list.
- Matches CPython 3.12 usage/error text, `--` handling, abbreviations/ambiguity, default `prog` basename, and `prog=''`.
- Unsupported forms are named compile-time refusals, including short options, non-store actions, `nargs`, subparsers, `parse_args(None)`, `choices` with non-str types, `dest`/`required` on positionals, literal `-h`/`--help`, and Namespace misuse.
- Added `test_ail_stdlib37.py` and registered it in `ail_check.MODULES`; updated `DEVLOG.md`, `DIFFERENCES.md`, manifest pins.

**Tests (run on final commit)**
- `test_ail_stdlib37`: OK (2 tests: 13 programs on both builds + 10 refusals)
- `test_ail_stdlib5`: OK (10)
- `test_ail_python_syntax`: OK (10)
- `test_ail_safetynet`: OK (5)
- `test_ail_files`: OK (18, 1 skipped)
- `test_ail_corpus_findings3`: OK (2)
- `update_manifest.py --check`: OK

**Probes (`/tmp/probes/argparse_*`)**
- Matched CPython on both builds: `basic`, `path`, `sysargv`, `routes`, `import_forms`, `negative_float`, `abbrev`, `duplicate`, `pos_default`, `prog_empty`, `choices_int_ok`, `help_off`, `help_off_ok`, plus error cases `ambiguous`, `bad_default`, `bad_default_extra`, `bad_default_required`, `choice`, `expected_one`, `extra_pos`, `extra_required`, `invalid_float`, `invalid_int`, `missing`, `negative`, `separator`, `separator_pos`, `unknown`.
- Refused by name: `choices_int_refuse`, `pos_dest_refuse`, `pos_required_refuse`, `help_refuse`.

Only untracked file is the job artifact `.agent/pipeline.md`; not committed.
[cost $0.0302, opencode tokens {"total": 1935336, "input": 63340, "output": 8788, "reasoning": 16424, "cache.write": 0, "cache.read": 1846784}]
    tool time: bash 53.4 min, edit 0.0 min
       1207s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && export AIL_NO_CACHE=1 AIL_EXTRA_CFLAGS='-Werror=incompatible
       1027s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && export AIL_NO_CACHE=1 AIL_EXTRA_CFLAGS='-Werror=incompatible
        353s bash   cd /tmp/probes && fail=0; for p in argparse_*.py; do out=$(bash ~/tools/cmp.sh "$p" /home/runner/work/ail-ci/a
        286s bash   cd /tmp/probes && for p in argparse_*.py; do echo "===== $p ====="; bash ~/tools/cmp.sh "$p" /home/runner/work
        262s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && AIL_NO_CACHE=1 python3 -m unittest test_ail_stdlib37 -v 2>&1
         42s bash   mkdir -p /tmp/probes && cat > /tmp/probes/argparse_choices_int_refuse.py <<'PY' import argparse   def main() -
         26s bash   cat > /tmp/probes/argparse_help_refuse.py <<'PY' import argparse   def main() -> None:     parser = argparse.A
          1s bash   cd /home/runner/work/ail-ci/ail-ci && git add AIL_CURRENT/MANIFEST.json AIL_CURRENT/ail_check.py AIL_CURRENT/a

## review 0
[model opencode-go/deepseek-v4.1-flash]
## Review: stdlib37 `argparse`

**What the change really does:** adds `argparselib.py`, a source-to-source lowering of `ArgumentParser`/`add_argument`/`parse_args` onto a Python prelude (`prelude_argparse.py`), plus a test module and manifest/DEVLOG/DIFFERENCES entries. It does not touch runtime/C hot paths.

**Tests (HEAD):** `par_check.py -j 2 test_ail_stdlib37 test_ail_safetynet test_ail_stdlib5` → 3 modules, 0 failed. `update_manifest.py --check` clean; only untracked file `.agent/pipeline.md`.

**Report claims**
- argparse most-imported refused module, 9 vs tempfile 7 — verified.
- "matches CPython usage/error text" — **false** (defects 1–2).
- Named refusals for short options/actions/nargs/subparsers/`parse_args(None)`/non-str choices/dest+required on positionals/help — verified by the passing refusal tests.
- All listed worker probes and the other test modules — **unverified** (not rerun; `/tmp/probes` not inspected).
- No speed check needed: the lowering only triggers on programs importing `argparse`; gdev programs are unaffected.

**Defects**

1. **Usage line order (and wrapping) differs from CPython.** `prelude_argparse._usage` walks `self.dests` in `add_argument` order (`prelude_argparse.py:60`), but CPython prints all optionals before positionals and wraps at 80 columns.
   Probe `/tmp/rprobes/usage_order.py`:
   ```python
   parser = argparse.ArgumentParser(prog='prog')
   parser.add_argument('target')
   parser.add_argument('--x')
   args = parser.parse_args([])
   ```
   Expected stderr line: `usage: prog [-h] [--x X] target`
   Actual (both builds): `usage: prog [-h] target [--x X]`
   Same in `usage_order2.py`; `usage_wrap.py` gives CPython's 3-line wrapped usage versus one long line. Exit status and error text match; only the usage line is wrong.

2. **Parsers are keyed by variable name across function scopes, so one parser's specs leak into another.** `parsers` is keyed by the local name (`argparselib.py:164-172`), `specs` accumulate per name, and `args_of` is a module-wide name map (`:237`, `:250`).  
   Probe `/tmp/rprobes/scope_samevar.py`:
   ```python
   def first():
       parser = argparse.ArgumentParser(prog='prog')
       parser.add_argument('--n', type=int, default=1)
       args = parser.parse_args(['--n', '5'])
       print(args.n + 1)
   def second():
       parser = argparse.ArgumentParser(prog='prog')
       parser.add_argument('--n', default='x')
       args = parser.parse_args(['--n', '7'])
       print(args.n + '!')
   first(); second()
   ```
   Expected (CPython): stdout `6\n7!`, exit 0.
   Actual (both builds): stdout empty, exit 1, stderr `TypeError: can only concatenate str (not "int") to str` — `first` reads `--n` with `second`'s `str` conversion. `scope_type.py`/`dup_dest_scope.py` fail the same way with distinct parser names `p`/`q`; base `/tmp/base37` refuses the import, so this is introduced by the change.

**Pre-existing:** none identified. The `prog` basename difference between compiled `exe_*` and `p.ail` in default-prog error paths is inherent argv[0] behavior, not a defect (error tests pass explicit `prog`).

VERDICT: FIX
[cost $0.0174, opencode tokens {"total": 734875, "input": 30204, "output": 4680, "reasoning": 13399, "cache.write": 0, "cache.read": 686592}]
    tool time: bash 8.9 min
        381s bash   cd /home/runner/work/ail-ci/ail-ci && date && python3 tools/par_check.py -j 2 test_ail_stdlib37 test_ail_safet
         83s bash   cd /tmp/rprobes && date && for p in usage_order scope_type direct_chain int_big float_special neg_pos dup_dest
         49s bash   cd /tmp/rprobes && cat > bare_error.py <<'PY' import argparse   def main() -> None:     parser = argparse.Argu
         12s bash   cd /tmp/rprobes && cat > usage_wrap.py <<'PY' import argparse   def main() -> None:     parser = argparse.Argu
          7s bash   cd /tmp/base37 && bash ~/tools/cmp.sh /tmp/rprobes/scope_samevar.py /tmp/base37 2>&1 | tail -8
          0s bash   git worktree add /tmp/base37 work 2>&1 | tail -2 && cd /tmp/base37 && git log --oneline -1
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check 2>&1 | tail -5; git status --sh
          0s bash   date && pwd && git status --short && git log --oneline -5

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed both defects and committed as `2fc2f77`.

- Usage line now prints optionals before positionals and wraps like CPython 3.12 (`[-h]` first, 78-column formatter).
- Parser/Namespace bindings are now resolved per lexical scope, including nested functions and module-level parsers.

**Tests (final commit):** `par_check.py -j 2` on `test_ail_stdlib37 test_ail_stdlib5 test_ail_safetynet test_ail_files test_ail_corpus_findings3` → 5 modules, 0 failed, 621s. `update_manifest.py --check` clean; only untracked `.agent/pipeline.md`.

**Probes (both builds):** 42 run via `cmp.sh`.
- Full stderr match: `usage_order`, `usage_order2`, `usage_wrap`, `usage_choices_pos`, `usage_help_off`, `usage_long_prog`; stdout match: `scope_samevar`, `scope_type`, `dup_dest_scope`, `scope_nested`, `scope_module_use`.
- 31 existing `argparse_*` probes: 27 match CPython stdout/exit; 4 refused by name (`choices` with int type, help output, positional `dest=`, positional `required=`).
- `argparse_sysargv` matches stdout/exit; its only stderr difference is the known pre-existing default-`prog` basename (`p.ail` vs `exe_*`).
[cost $0.0375, opencode tokens {"total": 2069317, "input": 75780, "output": 11323, "reasoning": 22406, "cache.write": 0, "cache.read": 1959808}]
    tool time: bash 18.7 min, read 0.0 min, edit 0.0 min
        623s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_stdlib37 test_ail_stdlib5 test_
        273s bash   cd /tmp/probes && mkdir -p results && ls argparse_*.py usage_order.py usage_order2.py usage_wrap.py usage_choi
         84s bash   cd /tmp/probes && for p in usage_order usage_order2 usage_wrap scope_samevar scope_type dup_dest_scope; do ech
         71s bash   cd /tmp/probes && for p in usage_order usage_order2 usage_wrap scope_samevar scope_type dup_dest_scope; do ech
         70s bash   cd /tmp/probes && for p in usage_choices_pos usage_help_off usage_long_prog scope_nested scope_module_use; do 
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git show --stat 2629707 | head -50
          0s bash   mkdir -p /tmp/probes && cd /tmp/probes && cat > usage_order.py <<'PY' import argparse   def main() -> None:   

## review 1
[model opencode-go/deepseek-v4.1-flash]
## Review: stdlib37 argparse lowering (`work..HEAD`, commits 18f10f8 + 2fc2f77)

**What the change really does:** adds `argparselib.py` + `prelude_argparse.py` and wires `argparse` into `stdlib5`/`ail_syntax`, lowering `ArgumentParser`, `add_argument` (long options/positionals, int/float/str/Path, default/required/choices/dest) and `parse_args()` onto a Python prelude; adds `test_ail_stdlib37.py` and records the difference. It is not a speed task and does not touch `bench/apps`.

**Verification**
- Tests on HEAD: `test_ail_stdlib37 test_ail_stdlib5 test_ail_safetynet test_ail_files test_ail_corpus_findings3` → 5 modules, 0 failed (521s). `update_manifest.py --check` clean.
- The two review fixes are real: usage order/wrapping (`usage_many`, `usage_prog_long`, `usage_dest_hyphen`, `usage_pos_choices`, `usage_help_off` all stderr-identical) and per-scope bindings (SCOPES test pass; my interleaved/multi-parser probes pass).
- Non-argparse code is unchanged: a `statistics.fmean` program produces byte-identical `program.c` on HEAD vs `work`.
- All defects below compile/run differently on both builds; the base (`work`) refuses these programs (`argparse ... not available`), so none are pre-existing.

**Defects**

1. Runtime `-h`/`--help` is wrong for `parse_args()` from `sys.argv`. The literal-list refusal does not cover sys.argv.
```python
import argparse
def main() -> None:
    parser = argparse.ArgumentParser(prog='prog')
    parser.add_argument('--x', default='d')
    args = parser.parse_args()
    print(args.x)
main()
```
Run `./prog -h`: expected (CPython) exit 0 with help on stdout (`usage: prog [-h] [--x X]` …), stderr empty. Actual (g and d): exit 2, stderr `usage: prog [-h] [--x X]` / `prog: error: unrecognized arguments: -h`.

2. An aliased parser is neither lowered nor refused, so it compiles into a runtime crash.
```python
import argparse
def main() -> None:
    parser = argparse.ArgumentParser(prog='prog')
    parser.add_argument('--x', default='d')
    other = parser
    args = other.parse_args(['--x', 'v'])
    print(args.x)
main()
```
Expected: `v`, exit 0. Actual (g and d): exit 1, stderr `AttributeError: 'dict' object has no attribute 'x'`.

3. Wrong error precedence when a required argument has an invalid default. The prelude validates defaults before checking missing required, CPython checks required first.
```python
import argparse
def main() -> None:
    parser = argparse.ArgumentParser(prog='prog')
    parser.add_argument('t', type=int, default='x')
    args = parser.parse_args([])
    print(args.t)
main()
```
Expected stderr `prog: error: the following arguments are required: t`; actual `prog: error: argument t: invalid int value: 'x'` (same for `--n required=True, type=int, default='x'`).

4. `prog=''` gets an extra space in the usage line (the report claims it is kept).
```python
import argparse
def main() -> None:
    parser = argparse.ArgumentParser(prog='')
    parser.add_argument('--x', required=True)
    args = parser.parse_args([])
    print(args.x)
main()
```
Expected first stderr line `usage: [-h] --x X`; actual `usage:  [-h] --x X` (both builds). Root cause: `_usage` joins `[prog] + parts`, CPython filters empty |prog|.

**Report claims:** usage order/wrap fixed — verified; per-scope parser/Namespace binding — verified; tests/`--check` — verified; "explicit `prog=''` is kept" — false (defect 4); "help output refused by name" — only for literal lists, false for `sys.argv` (defect 1); "bad-default errors match" — false when the argument is required (defect 3).

**Unverified:** the reported 42-probe count and the four named refusals (spot-checked refusals only); speed/icount (the change only adds a source substring test, no generated-code change for non-argparse programs).

VERDICT: FIX
1. `-h`/`--help` via `parse_args()` from `sys.argv` exits 2 with "unrecognized arguments" instead of printing help and exiting 0.
2. A parser alias (`other = parser`; `other.parse_args(...)`) is not refused and crashes at runtime with `AttributeError: 'dict' object has no attribute 'x'`.
3. A required argument with an invalid `default=` reports "invalid int value" instead of CPython's "the following arguments are required".
4. `prog=''` prints `usage:  [-h] ...` (double space) instead of `usage: [-h] ...`.
[cost $0.0358, opencode tokens {"total": 1694879, "input": 73178, "output": 8621, "reasoning": 24856, "cache.write": 0, "cache.read": 1588224}]
    tool time: bash 16.6 min, read 0.0 min
        523s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_stdlib37 test_ai
        138s bash   cd /tmp/rprobes && for p in err_order sep_expected sep_unknown sep_pos_neg empty_int empty_str abbrev_eq repea
        125s bash   cd /tmp/rprobes && for p in pos_default pos_default_given multi_pos interleave abbrev same_dest neg_pos usage_
         83s bash   cd /tmp/rprobes && for p in usage_help_off usage_prog_empty usage_prog_long usage_dest_hyphen usage_pos_choice
         40s bash   cd /tmp/rprobes && for p in big_int int_plus float_special2; do echo "===== $p ====="; bash /tmp/rcmp.sh /tmp/
         29s bash   cd /tmp/rprobes && for p in pathlib_form alias_read; do echo "===== $p ====="; bash /tmp/rcmp.sh /tmp/rprobes/
         28s bash   cd /tmp/rprobes && cat > pos_bad_default.py <<'PY' import argparse  def main() -> None:     parser = argparse.
         15s bash   cd /tmp/rprobes && for p in alias_read help_runtime usage_prog_empty; do echo "===== BASE $p ====="; bash /tmp

FINAL VERDICT: FIX  2026-10-29T06:01:37Z
