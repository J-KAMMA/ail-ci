# job job-stdlib8-10290216  started 2026-10-28T17:19:27Z  worker=oc reviewer=oc (GitHub)
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
Auto
Ultimate
Fast
Efficient
Sonus
Cantus
Qwen3.8-Max
Qwen3.8-Flash
Kimi-K3.1-Pro
Kimi-K2.8-Preview
GLM-5.3
GLM-5.3-Flash
DeepSeek-V4-Pro
DeepSeek-Flash
MiniMax-M3.1-Flash
DeepSeek-Flash -> ,"total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server_tool_use":{"web_search_requests":0,"web_fetch_requests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{},"permission_denials":[],"errors":["Operation aborted"],"terminal_reason":"aborted_streaming","fast_mode_state":"off","uuid":"6e94425d-fc82-4784-9379-93ceb4cd535f","session_id":"027694d4-c15b-4568-a94c-ea56caa949b4"}
DeepSeek-Flash -> ,"total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server_tool_use":{"web_search_requests":0,"web_fetch_requests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{},"permission_denials":[],"errors":["Operation aborted"],"terminal_reason":"aborted_streaming","fast_mode_state":"off","uuid":"6b040f21-92b5-4783-8c13-948fde39afeb","session_id":"fbac5394-a9a0-44cd-8bb4-5efb11fbef5f"}

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Committed `34ffd60` on `job-stdlib8-10290216`.

**Implementation:** `argparse` was the next most-imported refused module (9 imports, all in `language_examples`; 0 in `lab/corpus/programs`). Added `arglib.py` lowering `ArgumentParser` / `add_argument` / `parse_args` to plain Python over `list[str]` on both builds, registered `test_ail_stdlib8.py`, added DEVLOG + DIFFERENCES row `C?-job-stdlib8-10290216-1`.

**Tests on final commit (all pass):** `test_ail_stdlib8` 3, `test_ail_stdlib5` 10, `test_ail_check` 7, `test_ail_safetynet` 5, `test_ail_files` 18 (1 skipped), `test_ail_corpus_findings3` 2. Manifest `--check` exits 0.

**Probes:** 50 via `cmp.sh` on both builds — 35 match CPython, 15 refused by name, 0 mismatches.
- Match: `p_argparse_ok`, `p_argparse2`, `p_argparse_short`, `p_argparse_abbrev`, `p_argparse_alias`, `p_argparse_cluster`, `p_argparse_two`, `p_argparse_from`, `p_argparse_default_expr`, `p_argparse_defaults`, `p_argparse_choices_int`, `p_argparse_errors`, `p_argparse_routes`, `p_argparse_row`, `p_argparse_bad_int`, `p_argparse_bad_choice`, `p_argparse_missing`, `p_argparse_unknown`, `p8_cluster`, `p8_cluster2`, `p8_clusterval`, `p8_empty`, `p8_negok`, `p8_negpos`, `p8_negjunk2`, `p8_negval`, `p8_nondash`, `p8_noneliteral`, `p8_repeat`, `p8_routes`, `p8_choice_default`, `p8_strdefault`, `p8_strdefault3`, `p8_strdefault4`, `p8_swallow`.
- Refused by name: `p_argparse_append`, `p_argparse_dest`, `p_argparse_module`, `p_argparse_nested`, `p_argparse_nodefault`, `p_argparse_return`, `p_argparse_value`, `p_argparse_catch`, `p8_aliasparser`, `p8_cond`, `p8_condparse`, `p8_required_default`, `p8_strdefault2`, `p8_help`, `p8_negjunk`.

Declared remaining difference (in DIFFERENCES): argparse stderr usage/error text is not reproduced, and runtime `-h` over `sys.argv` is not CPython's help.
[cost $0.0653, opencode tokens {"total": 5408742, "input": 128453, "output": 18196, "reasoning": 32397, "cache.write": 0, "cache.read": 5229696}]
    tool time: bash 44.9 min
        788s bash   cd AIL_CURRENT run() { python3 -m unittest "$1" > "/tmp/test8_$1.log" 2>&1; echo "$1 rc=$?"; tail -3 "/tmp/tes
        437s bash   rm -rf /tmp/probes/final8; mkdir -p /tmp/probes/final8; for f in /tmp/probes/p_argparse*.py /tmp/probes/p8_*.p
        425s bash   rm -rf /tmp/probes/final8; mkdir -p /tmp/probes/final8; for f in /tmp/probes/p_argparse*.py /tmp/probes/p8_*.p
        177s bash   mkdir -p /tmp/probes/run8; for f in /tmp/probes/p_argparse*.py; do n=$(basename "$f" .py); { echo "### $n"; ba
        161s bash   python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/test_ail_stdlib8.py') s=p.read_text() old="""PRO
        155s bash   for n in p8_cluster p8_negval p8_swallow p8_empty p8_repeat p8_routes p_argparse_ok p_argparse_short p_argpars
         87s bash   for f in /tmp/probes/p8_*.py; do n=$(basename "$f" .py); { echo "### $n"; bash ~/tools/cmp.sh "$f" "$PWD"; } >
         84s bash   cd AIL_CURRENT && python3 -m unittest test_ail_stdlib8 -v 2>&1 | tail -60

## review 0
[model opencode-go/deepseek-v4.1-flash]
Review of `34ffd60` (work..HEAD). What the diff really does: it lowers one `parser = argparse.ArgumentParser(...)` assignment, its top-level `add_argument(...)` statements and `name = parser.parse_args(...)` per scope into ordinary Python: hidden variables per `dest` plus an argv-token loop; no runtime module. That matches the report's description.

**Claims**
- 9 `argparse` imports, none in `lab/corpus/programs`: verified.
- `arglib.py` lowering over `list[str]` on both builds, test registered, DEVLOG/DIFFERENCES row, manifest `--check` rc 0: verified.
- Tests I ran on HEAD: `test_ail_stdlib8`, `test_ail_stdlib5`, `test_ail_safetynet`, `test_ail_check`, `test_ail_corpus_findings3` all pass (0 failed). `test_ail_files` not re-run (unverified).
- Non-`argparse` programs: `--debug-dir` output identical to base (also a program containing only the string "argparse" is unchanged).
- "50 probes, 0 mismatches": true for the 7 listed probes I spot-checked, but the probe set misses the three failing forms below.
- "runtime `-h` is not CPython's help": verified, but it is an approximation, not a named refusal.

**Defects**

1. Repeated `parse_args` on the same parser in one scope aliases results and keeps stale defaults/flags. `arglib.py:219` emits defaults/flags once at `add_argument`, and `arglib.py:509-526` never resets them.
```
# /tmp/rprobes/p_multi.py
p = argparse.ArgumentParser(add_help=False)
p.add_argument('--x', default='a'); p.add_argument('--n', type=int, default=1)
a = p.parse_args(['--x', 'b', '--n', '2'])
b = p.parse_args([])
print(a.x, a.n, b.x, b.n)
```
CPython: `b 2 a 1` (exit 0); compiled general: `a 1 a 1`, default: `b 2 b 2` (exit 0).

2. A short option's attached value that begins with `-` is rejected. `_expand_lines` (`arglib.py:281`) splits the token before the parse, then the parse treats the value as an option.
```
# /tmp/rprobes/p_short_negvalue.py
p = argparse.ArgumentParser(add_help=False)
p.add_argument('-s', '--say', default='d')
print(repr(p.parse_args(['-s-vv']).say))
```
CPython: `'-vv'` (exit 0); compiled: exit 2, empty stdout (`-s=-vv` also fails).

3. Tokens after `--` are still cluster-expanded. `_expand_lines` runs on the whole argv before the `--` branch handles `arglib.py:363`.
```
# /tmp/rprobes/p_dash_cluster.py
p = argparse.ArgumentParser(add_help=False)
p.add_argument('-v', action='store_true'); p.add_argument('val')
a = p.parse_args(['--', '-vv'])
print(a.val, a.v)
```
CPython: `-vv False` (exit 0); compiled: exit 2, empty stdout (same for `-- -c7`).

4. Help is approximated rather than refused, contrary to "match exactly / otherwise refuse". A variable list containing `-h` is not the literal-list refusal case:
```
# /tmp/rprobes/p_help_var2.py
argv = ['-h']
a = p.parse_args(argv)
```
CPython prints full help (exit 0); compiled prints `usage: <path>` (exit 0). `--he` is worse: CPython help exit 0, compiled exit 2. This is declared in DIFFERENCES but the task allows no non-exact supported form.

**Pre-existing**
- `--n 999999999999999999999` with `type=int` stops with `integer overflow` (exit 1) vs CPython's big integer. The same runtime `int(...)` overflow reproduces on the base (`plainbig3.py`), so it is the general int64 limit, not this change.

**Unverified**
- `test_ail_files` (report claims 18 pass/1 skip).
- The remaining worker probes (spot-check only); speed check not applicable — the change adds no runtime hot path and only a compile-time substring test.

VERDICT: FIX
1. Reset defaults/flags per `parse_args` call, or refuse a second `parse_args` on the same parser (`/tmp/rprobes/p_multi.py`: expected `b 2 a 1`, got `a 1 a 1` / `b 2 b 2`).
2. Keep an attached short value intact (`/tmp/rprobes/p_short_negvalue.py`: expected `'-vv'`, got exit 2).
3. Do not cluster-expand tokens after `--` (`/tmp/rprobes/p_dash_cluster.py`: expected `-vv False`, got exit 2).
4. Refuse or reproduce help exactly instead of printing a usage line; `--he` currently exits 2 where CPython exits 0.
[cost $0.0400, opencode tokens {"total": 2175130, "input": 76566, "output": 8336, "reasoning": 28916, "cache.write": 0, "cache.read": 2061312}]
    tool time: bash 15.6 min
        280s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && date && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_
        209s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && date && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_c
        166s bash   cd /tmp/rprobes && cat > p_dash_value.py <<'EOF' import argparse  p = argparse.ArgumentParser(add_help=False) 
         79s bash   cd /home/runner/work/_temp/w2 && for n in p8_negpos p8_nondash p8_noneliteral p8_strdefault p_argparse_default
         47s bash   cd /home/runner/work/_temp/w2 && for f in /tmp/rprobes/p_*.py; do n=$(basename "$f" .py); echo "### $n"; timeo
         33s bash   cd /tmp/rprobes && cat > p_bigint.py <<'EOF' import argparse  p = argparse.ArgumentParser(add_help=False) p.ad
         31s bash   cd /home/runner/work/_temp/w2 && for n in p_bigint p_multi_flag p_multi_pos p_store_false; do echo "=== $n ===
         16s bash   cd /home/runner/work/_temp/w2 && for n in p_multi p_before p_multi_req p_neg_value; do echo "=== $n ==="; time

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed all four review defects and committed as `b812541`.

- Repeated `parse_args` on one parser now refused by name (no aliased/stale hidden variables).
- Attached short values stay intact: `-s-vv`, `-s=-vv`, negative and `--` values.
- Cluster expansion stops at `--`.
- Help is never approximated: runtime argv with `add_help=True`, literal `-h`/`--help`, and abbreviations like `--he` are refused by name.

Probes (`/tmp/probes/p8fix_*.py`, both builds, 13 total): 9 match CPython exactly, 4 refused by name. All required tests passed: `test_ail_stdlib8`, `test_ail_stdlib5`, `test_ail_check`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 6 modules, 0 failed. `update_manifest.py --check` rc 0.
[cost $0.0292, opencode tokens {"total": 1459335, "input": 62176, "output": 10168, "reasoning": 16111, "cache.write": 0, "cache.read": 1370880}]
    tool time: bash 11.3 min
        441s bash   cd AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_stdlib8 test_ail_stdlib5 test_ail_c
         74s bash   cd AIL_CURRENT && timeout 900 python3 -m unittest test_ail_stdlib8 -v 2>&1 | tail -30
         66s bash   cat > /tmp/probes/p8fix_short_negvalue.py <<'EOF' import argparse   def show(argv: list[str]) -> None:     p =
         66s bash   cd AIL_CURRENT && timeout 900 python3 -m unittest test_ail_stdlib8 -v 2>&1 | tail -40
         30s bash   mkdir -p /tmp/probes && cat > /tmp/probes/p8fix_multi.py <<'EOF' import argparse  p = argparse.ArgumentParser(
          0s bash   python3 tools/update_manifest.py && python3 tools/update_manifest.py --check; echo rc=$?; git diff --stat
          0s bash   pwd && git log --oneline -10 && git status
          0s bash   git add AIL_CURRENT/MANIFEST.json AIL_CURRENT/python/pkg-v12/arglib.py AIL_CURRENT/test_ail_stdlib8.py DEVLOG.

## review 1
[model opencode-go/deepseek-v4.1-flash]
Review of `work..HEAD` (`34ffd60`, `b812541`).

**What the change really does.** Adds `arglib.py`, a lowering pass that replaces a directly-written `ArgumentParser`/`add_argument`/`parse_args` with ordinary Python over a `list[str]` (no runtime module), wires it into `stdlib5.py`/`ail_syntax.py`, and adds `test_ail_stdlib8.py`, MANIFEST/DEVLOG/DIFFERENCES entries. `b812541` adds guards for a second `parse_args`, attached short values, cluster expansion after `--`, and help refusal. This matches the report's description.

**Report claims**
- Four review defects fixed: verified via the new test module (its attached-value, `--`, scope and help-refusal cases pass on both builds).
- 6 modules, 0 failed: verified by rerunning exactly `test_ail_stdlib8 test_ail_stdlib5 test_ail_check test_ail_safetynet test_ail_files test_ail_corpus_findings3` — 440s, 0 failed.
- `update_manifest.py --check` rc 0: verified.
- 9 `language_examples` / 0 `lab/corpus/programs` argparse imports: verified.
- 13-probe 9-match/4-refused tally: unverified (not rerun).
- "literal and expression defaults (a string default is converted as CPython does)" — **false** (defect 1).
- "everything else stays a named compile-time refusal" — **false** (defects 1–5 silently compile to wrong output).
- Non-argparse C unchanged: verified with `--debug-dir` on base vs HEAD (`program.c` identical for a plain program and one containing "argparse" in a comment/string).

**Defects**

1. Dynamic string defaults are not converted (`/tmp/rprobes/r8_dyndflt.py`, `r8_dyndflt2.py`).
```python
d = '5'
p.add_argument('--n', type=int, default=d)
a = p.parse_args([]); print(a.n, type(a.n).__name__)
```
Expected `5 int`; actual `5 str` (also via list item, dict value, attribute and function argument). With `type=Path, default=d` CPython prints the path name; AIL raises `AttributeError: 'str' object has no attribute 'name'` (exit 1).

2. A single-dash multi-char option that shares its first letter with a short option is cluster-expanded wrongly (`r8_multi3.py`).
```python
p.add_argument('-f', action='store_true'); p.add_argument('-foo', default='x')
a = p.parse_args(['-foo=bar']); print(a.f, a.foo)   # then ['-foobar']
```
Expected `False bar` then exit 2 (`-foobar` unrecognized); actual `True bar` and `True bar`, exit 0.

3. `add_argument` after `parse_args` is silently applied to the earlier namespace (`r8_addafter.py`).
```python
p.add_argument('--a', default='x'); a = p.parse_args([])
p.add_argument('--b', default='y'); print(a.a, a.b)
```
Expected `AttributeError`; actual `x y` (both builds, exit 0).

4. `parse_args(None)` compiles but crashes (`r8_parsenone.py`).
```python
p.add_argument('--n', type=int, default=1); a = p.parse_args(None); print(a.n)
```
Expected `1`, exit 0; actual `TypeError: object of type 'NoneType' has no len()`, exit 1 on both builds.

5. Negative-number-looking option names longer than two characters are not refused and change negative-token handling (`r8_negopt2.py`).
```python
p.add_argument('-12', type=int, dest='twelve', default=0)
p.add_argument('--n', type=int, default=0)
print(p.parse_args(['--n', '-5']).n)
```
Expected exit 2 (`--n: expected one argument`); actual prints `-5 0` and exits 0 (same for a positional `-5`).

**Pre-existing** (base `/tmp/basework`): `Path` prints `_AilPath` rather than `PosixPath` (`r8_plainpath2.py`); runtime `int()` of a dynamic string outside int64 stops with `integer overflow` (`r8_plain_dynint.py`), which the `--n 9223372036854775808` argparse probe inherits although the new DIFFERENCES row does not declare it. Minor over-refusal (named, accepted): any literal short token containing `h` is treated as help, so `-s-hi` is refused although CPython parses it and does not print help.

**Unverified**: the exact 13 `p8fix_*` probe results; speed (no hot/runtime code changed, so no icount was taken); wider suite (per instructions).

VERDICT: FIX
[cost $0.0551, opencode tokens {"total": 2568595, "input": 95625, "output": 10741, "reasoning": 45077, "cache.write": 0, "cache.read": 2417152}]
    tool time: bash 10.2 min
        441s bash   date; cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 1500 python3 ../tools/par_check.py -j 2 test_ail_st
         53s bash   cd /tmp/rprobes; for p in r8_*.py; do echo "=== $p"; bash ~/tools/cmp.sh /tmp/rprobes/$p /home/runner/work/_te
         53s bash   cd /tmp/rprobes cat > r8_intchoice.py <<'EOF' import argparse  def good() -> None:     p = argparse.ArgumentPa
         12s bash   cd /tmp/rprobes cat > r8_dyndflt2.py <<'EOF' import argparse from pathlib import Path  class C:     text = '5'
          8s bash   python3 - <<'EOF' import argparse for desc, setup in [   ('name', "d='5'"),   ('list', "d=['5']"),   ('dict', 
          7s bash   cd /tmp/rprobes cat > r8_negopt2.py <<'EOF' import argparse  def val() -> None:     p = argparse.ArgumentParse
          6s bash   cd /tmp/rprobes cat > r8_parsenone.py <<'EOF' import argparse  p = argparse.ArgumentParser(add_help=False) p.a
          6s bash   cd /tmp/rprobes; cat > r8_plainpath2.py <<'EOF' from pathlib import Path x = Path('/tmp/base') print(type(x)._

FINAL VERDICT: FIX  2026-10-28T19:57:21Z
