# job job-std_argparse-11011519  started 2026-11-01T06:30:24Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Done, committed as `7bee3c1` (not pushed).

- Added bundled `AIL_CURRENT/stdlib/argparse.py` and 12 realistic programs in `lab/stdlib/argparse/` with `RESULTS.md`.
- **10/12 build** (general path) and match CPython stdout/exit; `errtool.py` (caught `SystemExit`) and `subcmd.py` (`add_subparsers`) are documented follow-ups with exact refusal text.
- Fixed append default copying, `parse_known_args` extras order, `format_usage`, and added `int`/`str`/`float` as builtin values.
- Generated C for all 10 lab/compare tasks is byte-identical to base for both syntaxes, including `--exact-int` for `rail_transfer` and `chain_relax`.
- Added `test_ail_std_argparse.py` via `tests.d`; passes on default and forced-general builds.

Tests on final commit: `test_ail_std_argparse` pass, `test_ail_safetynet` 5/5, `test_ail_files` 18 pass (1 skip), `test_ail_corpus_findings3` 2/2. `update_manifest.py --check` passes, SDK export includes `stdlib/argparse.py`.

Probes (both builds, all matched CPython): `ap_core`, `ap_negative`, `ap_values`, `ap_known`, `ap_err_choice`, `ap_err_group`, `ap_err_int`, `ap_err_required`, `ap_err_unknown`, `builtins_values`.
[cost $0.0920, opencode tokens {"total": 8449760, "input": 240100, "output": 22614, "reasoning": 29990, "cache.write": 0, "cache.read": 8157056}]
    tool time: bash 74.1 min, edit 0.0 min, read 0.0 min
        547s bash   python3 - <<'PY' p='/tmp/probes/compare_c.py' s=open(p).read() s=s.replace("d=Path('/tmp/ccmp')/tag/task","d=P
        481s bash   cat > /tmp/probes/compare_c.py <<'PY' import subprocess, sys, os, glob, hashlib from pathlib import Path repo=
        417s bash   cd /home/runner/work/_temp/w2 && for f in /tmp/probes/ap_*.py /tmp/probes/builtins_values.py /tmp/probes/argpa
        411s bash   cd /home/runner/work/_temp/w2 && rm -f /tmp/t1.rc /tmp/t2.rc; (python3 AIL_CURRENT/test_ail_std_argparse.py > 
        333s bash   python3 - <<'PY' p='AIL_CURRENT/test_ail_std_argparse.py' s=open(p).read() s=s.replace('''                    
        317s bash   cd /home/runner/work/_temp/w2 && rm -f /tmp/t3.rc /tmp/t4.rc; (python3 AIL_CURRENT/test_ail_files.py > /tmp/t_
        302s bash   cat > AIL_CURRENT/test_ail_std_argparse.py <<'PY' """The bundled `argparse` module: the twelve realistic CLI p
        259s bash   cd /home/runner/work/_temp/w2 && for f in /tmp/probes/ap_core.py /tmp/probes/ap_negative.py /tmp/probes/ap_val

## review 0
[model opencode-go/deepseek-v4.1-flash]
Reviewed `git diff work..HEAD` (commit `7bee3c1`) against base `work` (4b30106). The change really adds a bundled 819-line `AIL_CURRENT/stdlib/argparse.py`, admits `int`/`str`/`float` as first-class builtin values in `pyboxed2.py`, adds 12 lab programs/results and a test, and widens `update_manifest.py` to pin `stdlib/*`. The report's "fixed format_usage" claim is misleading: `format_usage` is new code, and it is not CPython-correct.

**What I ran**
- `bash ~/tools/cmp.sh <probe> $PWD` on 4 new probes, both builds; base refuses all argparse probes (`argparse.ArgumentParser (not yet published...)`), so the differences below are caused by this change.
- `python3 ../tools/par_check.py -j 2 test_ail_std_argparse test_ail_safetynet`: 2 modules, 0 failed (465s).
- `python3 tools/update_manifest.py --check`: rc 0.
- Spot-checked generated C vs `/tmp/base_arg`: `berth_sim` python and `echo_pack` ail hashes identical.

**Verified claims**
- 10/12 build and match CPython on both builds: verified by the passing test.
- Refusals for `errtool`/`subcmd` name the feature: verified by the passing test.
- append default copying and extras ordering: verified (rp2 append result correct; rp3 extras `['--bad','pos2']` matched).
- `int`/`str`/`float` as builtin values through list/dict/attribute/argument: verified (worker's `builtins_values.py`, both builds identical).
- Generated C byte-identical: spot-verified; worker's full `compare_c2.out` is all-OK.
- Not re-run (out of reviewer scope): `test_ail_files`, `test_ail_corpus_findings3`; no speed check (only dict/membership changes on non-hot path).

**Defects (confirmed with probes, both builds)**
1. A string default is not converted by `type=`. Probe rp1/RP2: `p.add_argument("--n", type=int, default="5")`; expected `5 int`, actual `5 str`.
2. `nargs="*"` positional default is discarded when no arguments are given. rp1: `p.add_argument("xs", nargs="*", default=["D"])`; expected `xs ['D']`, actual `xs []`.
3. Required mutually exclusive group usage uses `[...]`, not CPython's `(...)`. rp4: expected `usage: tool [-h] --req REQ (--a | --b) [rest ...]`, actual `... [--a | --b] ...`.
4. Help text for a parser whose longest invocation is short is moved to an indented next line. rp4: expected `  -h, --help  show this help message and exit`, actual `  -h, --help\n              show this help message and exit`.

VERDICT: FIX
1. `type=` must convert string defaults. Probe: `import argparse; p=argparse.ArgumentParser(prog="p"); p.add_argument("--n", type=int, default="5"); a=p.parse_args([]); print(a.n, type(a.n).__name__)` — expected `5 int`, actual `5 str`.
2. `nargs="*"` positional default must survive an empty command line. Probe: `p=argparse.ArgumentParser(prog="p"); p.add_argument("xs", nargs="*", default=["D"]); print(p.parse_args([]).xs)` — expected `['D']`, actual `[]`.
3. Required mutually exclusive groups must render with parentheses in usage. Probe: `p=argparse.ArgumentParser(prog="tool"); g=p.add_mutually_exclusive_group(required=True); g.add_argument("--a", action="store_true"); g.add_argument("--b", action="store_true"); print(p.format_usage(), end="")` — expected `usage: tool [-h] (--a | --b)`, actual `usage: tool [-h] [--a | --b]`.
4. Help text must stay on the invocation line when it fits. Probe: `p=argparse.ArgumentParser(prog="tool"); p.add_argument("--req", required=True, help="needed"); print(p.format_help(), end="")` — expected `  --req REQ   needed`, actual `  --req REQ\n              needed`.
[cost $0.0260, opencode tokens {"total": 1139392, "input": 60241, "output": 5240, "reasoning": 17783, "cache.write": 0, "cache.read": 1056128}]
    tool time: bash 12.2 min
        467s bash   date; cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_std_argparse test_ail_safetynet > /tmp/rev
        120s bash   cd AIL_CURRENT && nohup python3 ../tools/par_check.py -j 2 test_ail_std_argparse test_ail_safetynet > /tmp/rev
         93s bash   date; for n in 1 2 4; do echo "##### rp$n"; bash ~/tools/cmp.sh /tmp/rprobes/rp$n.py $PWD 2>&1 | tail -40; don
         47s bash   cat > /tmp/rprobes/ccmp.py <<'PY' import subprocess, sys, os, hashlib from pathlib import Path repo=Path('/hom
          4s bash   date; for n in 1 4; do echo "##### base rp$n"; bash ~/tools/cmp.sh /tmp/rprobes/rp$n.py /tmp/base_arg 2>&1 | t
          1s bash   git worktree add /tmp/base_arg work 2>&1 | tail -3; git -C /tmp/base_arg rev-parse --short HEAD; ls /tmp/base_
          0s bash   date; cat /tmp/probes/builtins_values.py; echo ===; python3 tools/update_manifest.py --check 2>&1 | tail -10; 
          0s bash   git -C /tmp/base rev-parse --short HEAD; git rev-parse --short work; git -C /tmp/base status --short | head; l

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed all four review defects in `AIL_CURRENT/stdlib/argparse.py` and committed as `c55a755`.

- `type=` now converts string defaults (type-only where CPython does that; positional `nargs="?"` also checks choices).
- Positional `nargs="*"` keeps a non-`None` default when empty; optional forms unchanged.
- Required mutually exclusive groups render as `(...)`; optional groups stay `[...]`.
- Help text stays on the invocation line when it fits, using CPython's column test and wrap width.
- Also fixed `append`/`append_const` defaults that are not lists, so they fail like CPython instead of becoming character lists.

Verification on final commit `c55a755`:
- 11/11 probes match CPython on both builds (stdout + exit code; stderr for error probes): `rp1_defaults`, `rp1e_badint`, `rp1e_badchoice`, `rp2_star`, `rp2e_star_choice`, `rp2e_missing`, `rp3_mutex`, `rp4_help`, `rp5_values`, `rp6_edges`, `rp7_suppress`.
- `test_ail_std_argparse`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: 4 modules, 0 failed (448s).
- `tools/update_manifest.py --check`: rc 0.
- Generated C for all 10 `lab/compare` tasks, Python and AIL: 0 differences vs base.
[cost $0.0410, opencode tokens {"total": 3088012, "input": 91692, "output": 13575, "reasoning": 16985, "cache.write": 0, "cache.read": 2965760}]
    tool time: bash 49.3 min
        533s bash   cd /tmp && sed 's#/tmp/baseail#/tmp/base_arg#; s#/tmp/ccmp2#/tmp/ccmp3#' /tmp/probes/compare_c.py > /tmp/probe
        449s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && git rev-parse --short HEAD && date && python3 ../tools/par_check.
        449s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_safetynet tes
        430s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_std_argparse 
        315s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_std_argparse 
        287s bash   cd /home/runner/work/_temp/w2 && for p in rp1_defaults rp1e_badint rp1e_badchoice rp2_star rp2e_star_choice rp
        159s bash   cd /home/runner/work/_temp/w2 && python3 tools/update_manifest.py >/dev/null && for p in rp6_edges rp1_default
        158s bash   cd /home/runner/work/_temp/w2 && for p in rp1_defaults rp1e_badint rp1e_badchoice rp2_star rp2e_star_choice rp

## review 1
[model opencode-go/deepseek-v4.1-flash]
**What the change does:** adds a bundled 851-line `AIL_CURRENT/stdlib/argparse.py`, compiler support for `int`/`str`/`float` as builtin values, 12 CLI programs, a registered test, and manifest stdlib pinning.

**Report claims**
- 11/11 probes match CPython: verified (reran all 11 on HEAD; both builds, stdout + exit).
- 10/12 lab programs build/match: verified by `test_ail_std_argparse`.
- 4 review fixes: default conversion, positional `*` default, action-help column/wrap, append default verified. Required-mutex usage is only partly fixed (defect 1).
- `update_manifest.py --check`: verified rc 0.
- 4 test modules pass: `test_ail_std_argparse` + `test_ail_safetynet` rerun, 0 failed (309s). `test_ail_files`/`corpus_findings3` not rerun.
- lab/compare C byte-identical: unverified (codegen pins unchanged).
- Base has no `stdlib/argparse.py`, so none of the differences below are pre-existing.

**Defects**
1. Required mutually-exclusive groups with `nargs="?"`/`"*"` lose the inner bracket: `.strip("[]")` in `_group_piece` (`argparse.py:126`).
   Probe `/tmp/rprobes/r_mutexq.py`: required group `--foo nargs="?"`, `--bar nargs="*"`.
   Expected: `usage: tool [-h] (--foo [FOO] | --bar [BAR ...])` and `usage: tool [-h] --foo [FOO]`.
   Actual: `usage: tool [-h] (--foo [FOO | --bar [BAR ...)` and `usage: tool [-h] --foo [FOO`.

2. `nargs=argparse.REMAINDER` is silently mis-parsed; unknown option-looking tokens become extras.
   Probe `/tmp/rprobes/r_rem.py`: positional `rest` / optional `--rest` with `nargs=argparse.REMAINDER`, argv `["--cmd","x","a","--b","c"]` and `["--rest","a","--b","c"]`.
   Expected (exit 0): `Namespace(cmd='x', rest=['a', '--b', 'c'])` and `Namespace(rest=['a', '--b', 'c'])`.
   Actual: exit 2, no stdout, `p: error: unrecognized arguments: --b` (both builds).

3. Explicit value with `nargs=<int>` does not validate the count.
   Probe `/tmp/rprobes/r_expl.py`: `p.add_argument("--pair", nargs=2); print(p.parse_args(["--pair=k"]))`.
   Expected: exit 2, stderr `p: error: argument --pair: expected 2 arguments`, no stdout.
   Actual: exit 0, stdout `Namespace(pair=['k'])` (both builds).

4. Description/epilog wrapping is one column too wide (`_wrap(...,79,0)` vs CPython's 78).
   Probe `/tmp/rprobes/r_desc.py`: `text="x"*70+" "+"y"*8`, description and epilog.
   Expected: two lines (`x`*70, then `yyyyyyyy`).
   Actual: one 79-character line `xxxx… yyyyyyyy` (both builds).

5. `argument_default` is ignored for `store_true`/`count` (and other flag actions) in `_ail_add`.
   Probe `/tmp/rprobes/r_argdef.py`: `ArgumentParser(argument_default=5)` with `store_true`, `count`, `store`.
   Expected: `Namespace(flag=5, count=5, name=5)` and `Namespace(flag=True, count=6, name=5)`.
   Actual: `Namespace(flag=False, count=None, name=5)` and `Namespace(flag=True, count=1, name=5)`.

Unverified: all 10 lab/compare C hashes; stderr equality on the error probes; `test_ail_files` and `test_ail_corpus_findings3`.

VERDICT: FIX
[cost $0.0375, opencode tokens {"total": 1844347, "input": 72165, "output": 4749, "reasoning": 30985, "cache.write": 0, "cache.read": 1736448}]
    tool time: bash 12.3 min
        311s bash   date; cd /home/runner/work/_temp/w2/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_std_argparse te
        282s bash   date; cd /home/runner/work/_temp/w2 && for p in rp1_defaults rp1e_badint rp1e_badchoice rp2_star rp2e_star_cho
        118s bash   date; cd /home/runner/work/_temp/w2 && for p in r_mutexq r_desc r_rem r_expl r_argdef; do echo "######## $p"; 
         22s bash   date; cd /home/runner/work/_temp/w2 && bash ~/tools/cmp.sh /tmp/probes/rp4_help.py $PWD 2>&1 | tail -40
          2s bash   date; cd /home/runner/work/_temp/w2 && python3 tools/codegen_diff.py --base work 2>&1 | tail -20; date
          0s bash   date; cd /home/runner/work/_temp/w2 && python3 tools/update_manifest.py --check >/tmp/manifest_check.log 2>&1;
          0s bash   cd /tmp && mkdir -p rprobes && cat > /tmp/rprobes/r_mutexq.py <<'PY' import argparse  p = argparse.ArgumentPar
          0s bash   for args in '--pair=k v' '--pair=k v w' '--items=a b' '--items=a'; do echo "== $args"; python3 -c " import arg

FINAL VERDICT: FIX  2026-11-01T10:07:26Z
