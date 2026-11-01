# job job-covenv2-11011011  started 2026-11-01T01:12:33Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Implemented and verified on branch `job-covenv2-11011011`.

**Commits**
- `a4a0183` initial `os.environ.get(key)` / `Path.home()` support
- `68c334c` fixed general-path key hoisting, added loop/container and HOME edge-case tests
- `2383ad7` inject the general-path env-or-None helper only where needed

**Checks**
- Manifest: `python3 tools/update_manifest.py --check` passes.
- Final commit tests: `test_ail_covenv` 5/5, `test_ail_safetynet` 5/5, `test_ail_files` 18/18 (1 skip), `test_ail_corpus_findings3` 2/2.
- Generated C vs base `0b0a5fe`: all 10 lab/compare `main.ail` builds byte-identical; `main.py` identical for the 7 that build, the same 3 (`scar_life`, `tally_lang`, `tree_fold`) refuse identically on both.

**Probes** (all in `/tmp/probes`, run via `~/tools/cmp.sh` unless noted)
- Env probes, 27 files (`p_env_basic/or/and/compare/types/once/getenv/default_none/default_str/sources/src_a..e/loop1..4/comb1..5/containers/comprehension/statement`): PASS default+general under both env scenarios; typed-only runs PASS or refuse by name, no output mismatch.
- Home probes (`p_home_typed/root/relative/plain`) across HOME set, unset, empty, trailing/internal `//`, `//foo`, `///foo`, relative, `.`, `..`, and spaces: PASS default+general. Typed `p_home_typed` PASS for all 10 HOME variants; `p_home_root/relative` typed refusals are the pre-existing `list(p.parts)` limitation, refused by name.
- Found and fixed a real regression: the first general-path lowering hoisted `os.environ.get(keys[i])` key evaluation before its `for`, reading `i` unbound. It now evaluates the key once inside `_ail_environ_get_or_none`; regression test `ENV_LOOP` covers loops, lists, dicts and `os.getenv`.
[cost $0.0834, opencode tokens {"total": 8718447, "input": 180225, "output": 21961, "reasoning": 29477, "cache.write": 0, "cache.read": 8486784}]
    tool time: bash 76.0 min, edit 0.0 min
        621s bash   bash /tmp/cmpgen.sh 2>&1 | tee /tmp/cmpgen-result2.txt | tail -30; echo "fail=${PIPESTATUS[0]}"
        558s bash   cat > /tmp/cmpgen.sh <<'EOS' #!/bin/bash set -u REPO=/home/runner/work/ail-ci/ail-ci BASE=/tmp/ailbase OUT=/tm
        285s bash   cd /home/runner/work/ail-ci/ail-ci && : > /tmp/probes-home-final.txt; for h in '/tmp//covhome///dir//' 'relhom
        246s bash   timeout 2400 python3 -m unittest test_ail_corpus_findings3 2>&1 | tail -15
        235s bash   timeout 2400 python3 -m unittest test_ail_corpus_findings3 2>&1 | tail -8
        224s bash   timeout 2400 python3 -m unittest test_ail_safetynet 2>&1 | tail -15
        176s bash   timeout 2400 python3 -m unittest test_ail_safetynet 2>&1 | tail -8
        170s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && (timeout 2400 python3 -m unittest test_ail_safetynet 2>&1 | 

## review 0
[model opencode-go/deepseek-v4.1-flash]
## Review: covenv2 (`os.environ.get(key)`, `Path.home()`)

**What the change really does:** optlib lowers `os.environ.get(key)` with no default to a `(hasenv, getenv)` pair on the typed path (with `or`/truth/`is None` handling), otherwise returns the source so the general path builds it; filelower's general path emits `_ail_environ_get_or_none(key)` instead of refusing; `Path.home()` becomes `_ail_pl_norm(_ail_pp_home())` backed by a new `ailf_home` in `ailpath_core.h`. This matches the report.

**Verified**
- Env probes (present/absent/empty, `is None`, truth, `not`, `or`, `== ""`, `==`/`in`, method, list/dict/attribute/argument, loop index/loop var, side-effecting key evaluated once, comprehension, `while`, nested def/lambda, mutation via `os.environ[...]`, module-level, `os.getenv`): default and general match CPython; typed-only matches for the supported uses and refuses by name otherwise.
- Home probes (`HOME` unset/empty/trailing/internal `//`, `//foo`, `///foo`, bare `//`, `///`, relative, `.`, `..`, spaces, `/`): all builds match CPython except the `~` case below.
- Generated C: all 10 `lab/compare/src/*/main.ail` byte-identical to base; `main.py` hashes identical for the 7 that build (using `--exact-int` for `chain_relax`/`rail_transfer`), the other 3 refuse identically.
- Tests on HEAD: `test_ail_covenv`, `test_ail_files`, `test_ail_pathlib`, `test_ail_corpus_findings3`, `test_ail_safetynet` all pass (5/5 modules, 529s). `update_manifest.py --check` rc 0.
- Report claims otherwise check out; the only discrepancy is an untested `HOME` boundary.

**Pre-existing (identical on base, non-blocking)**
- `Path` values in a dict after a list print as a pointer (`p_path_listdict.py`), and `.name` off a dict-held `Path` raises `AttributeError: '_AilPath' object has no attribute 'name'`; reproduced on base with `Path("/tmp/x")`.
- Non-UTF-8 env value (`RP_BAD=$'\xff'`): general path raises `UnicodeDecodeError`, typed prints `'ÿ'` vs CPython `'\udcff'`; identical for `os.environ.get(k, default)` on base.

**Unverified:** Windows `Path.home()` branch (`HOME` vs `USERPROFILE`/`HOMEDRIVE` rules); speed not measured because generated C for all non-feature programs is byte-identical (no hot-code change).

VERDICT: FIX

1. `Path.home()` does not raise when `HOME` starts with `~` (e.g. `HOME='~'`, `HOME='~/x'`, `HOME='~~'`). CPython's `Path.home()` is `cls("~").expanduser()`, which raises `RuntimeError: Could not determine home directory.` (exit 1, empty stdout). `ailf_home` returns the value and `_ail_pl_norm` keeps it, so both builds print it and exit 0. Probe (`/tmp/rprobes/p_home_tilde.py`, run with `HOME='~'`):
   ```python
   from pathlib import Path

   def main() -> None:
       print(str(Path.home()))

   main()
   ```
   Expected: no stdout, stderr `RuntimeError: Could not determine home directory.`, exit 1.
   Actual (`g` and `d`): stdout `~`, exit 0. Same for `HOME='~/x'` (`~/x`) and `HOME='~~'` (`~~`). Fix: after expanding, reject a result whose first character is still `~` and fail the way `expanduser` does.
[cost $0.0491, opencode tokens {"total": 3393043, "input": 107879, "output": 13288, "reasoning": 25412, "cache.write": 0, "cache.read": 3246464}]
    tool time: bash 21.1 min
        530s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1800 python3 ../tools/par_check.py -j 2 test
        370s bash   cat > /tmp/rprobes/cmp_cpy.sh <<'EOS' #!/bin/bash task=$1 for w in /home/runner/work/ail-ci/ail-ci /tmp/base; 
         63s bash   cd /home/runner/work/ail-ci/ail-ci && date && for h in UNSET '' '/tmp//rh///dir//' '//rh' '///rh' 'rel' '.' '.
         62s bash   cat > /tmp/rprobes/cmp_c.sh <<'EOS' #!/bin/bash task=$1 for w in /home/runner/work/ail-ci/ail-ci /tmp/base; do
         44s bash   cd /home/runner/work/ail-ci/ail-ci && for task in chain_relax rail_transfer; do for w in "$PWD" /tmp/base; do 
         35s bash   cd /home/runner/work/ail-ci/ail-ci && date && export RP_KEY=value RP_EMPTY= && unset RP_MISS && for p in /tmp/
         26s bash   cd /tmp/rprobes && cat > p_path_dict.py <<'EOF' from pathlib import Path   def main() -> None:     d = {"h": P
         25s bash   cd /tmp/rprobes && cat > p_path_listdict.py <<'EOF' from pathlib import Path   def main() -> None:     ps = [P

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed the review defect and committed as `e6fd7d5`.

**Change:** `Path.home()` now routes through a new `_ail_pl_home` prelude helper that raises `RuntimeError: Could not determine home directory.` when the expanded HOME text still starts with `~`, matching `cls("~").expanduser()`.

**Probes** (`bash ~/tools/cmp.sh`, default + general):
- HOME `~`, `~/x`, `~~`, `~//`: both builds now stdout-empty, exit 1, same RuntimeError as CPython.
- HOME `/~`, `/tmp//probe///a//`, `.`, `..`, `/`, empty, unset: stdout/exit match CPython (exit 0).
- `Path.home() / "a"`, nested joins, f-string use: match.
- Env probes (present/absent/empty, `or`, `is None`, direct/str): match.
- Typed-only path covered by the new tilde cases in `test_ail_covenv`.

**Generated C:** all 10 `lab/compare/src/*/main.ail` SHA-256 hashes byte-identical to `/tmp/base`.

**Tests on the committed contents:** `test_ail_covenv`, `test_ail_pathlib`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 5/5 pass, 0 failed (591s). `update_manifest.py --check` rc 0. DEVLOG updated; no DIFFERENCES row needed.
[cost $0.0298, opencode tokens {"total": 2350036, "input": 90518, "output": 7148, "reasoning": 8658, "cache.write": 0, "cache.read": 2243712}]
    tool time: bash 12.0 min, edit 0.0 min
        592s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1800 python3 ../tools/par_check.py -j 2 test
         57s bash   cd /home/runner/work/ail-ci/ail-ci && for spec in \   "tilde|p_home.py|HOME=~" \   "tilde_join|p_home_join.py|
         49s bash   cat > /tmp/gen_c.py <<'EOF' import sys, json, hashlib root, paths = sys.argv[1], sys.argv[2:] sys.path[:0] = [
         17s bash   cd /home/runner/work/ail-ci/ail-ci && echo "=== home_unset" && env -u HOME bash ~/tools/cmp.sh /tmp/probes/p_h
          1s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' from pathlib import Path p=Path('DEVLOG.md') t=p.read_t
          1s bash   cd /tmp && python3 -V && for h in '~' '~/x' '~~' 'x~'; do echo "HOME=[$h]"; HOME="$h" python3 -c 'from pathlib
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git status --short && git diff --stat && python3 tools/update_manifest.p
          0s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1200 python3 ../tools/par_check.py -j 2 test

## review 1
[model opencode-go/deepseek-v4.1-flash]
**Review report**

**What the change really does.** It adds no-default `os.environ.get(key)` lowering (typed `hasenv`/`getenv` pair in optlib, `_ail_environ_get_or_none` for the general path, plus the `environ.get` trigger) and a new `Path.home()` primitive whose prelude wrapper raises `RuntimeError: Could not determine home directory.` when the HOME text still starts with `~`. The worker report only describes the latest `Path.home()` tilde fix; the env support is in the earlier commits and DEVLOG. No contradiction, just a scoped report.

**Probes** (all `bash ~/tools/cmp.sh`, default + general, compared with CPython):
- Env: basic present/empty/absent, direct uses, key via variable/list item/attribute/dict value/argument, chained `or`, containers, defaults, odd keys (`""`, `"A=B"`, spaces, unicode, newline value), value via attribute/list/dict, `is`/`is not`/`==`, side-effecting key, `and`/conditional/`while`. All stdout/exit match; keys evaluated once.
- Path: `home1` over 18 HOME values (unset, empty, `/`, `//`, `//foo//`, `/tmp//x///`, `.`, `..`, relative, `~`, `~/x`, `~~`, `~//`, `/~`, `x~`, spaces, unicode, `///`, `////foo`), `home2` (`pathlib.Path.home`), `home3`, joins/parent/name/f-string. All match; `~`-leading HOME exits 1 with the CPython RuntimeError on both builds.
- Feature-free programs (`home_plain`, `env_plain` with a default) match.
- Generated C: 10/10 `lab/compare/src/*/main.ail` byte-identical to `/tmp/base`; 7/7 buildable `main.py` identical. `scar_life/tally_lang/tree_fold` `main.py` fail on base too (unrelated `re`/tuple/locals limitations) — pre-existing.
- Tests on HEAD: `test_ail_covenv`, `test_ail_pathlib`, `test_ail_files`, `test_ail_safetynet`, `test_ail_corpus_findings3` — 5/5 pass; `update_manifest.py --check` rc 0.

**Claims:** all verified (test duration differs slightly; pass/fail and counts match). Speed check not needed: feature-free generated C is byte-identical and the new runtime path is only reached by these calls.

**Unverified:** Windows `_WIN32` HOME/USERPROFILE branch, and a passwd entry missing when HOME is unset.

VERDICT: ACCEPT
[cost $0.0281, opencode tokens {"total": 1417650, "input": 64463, "output": 7408, "reasoning": 16627, "cache.write": 0, "cache.read": 1329152}]
    tool time: bash 23.0 min
        456s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/gcall && mkdir -p /tmp/gcall && fail=0; for t in berth_sim c
        422s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1500 python3 ../tools/par_check.py -j 2 test
        263s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check; echo MANIFEST_RC=$?; cd AIL_CU
         89s bash   cd /home/runner/work/ail-ci/ail-ci && for h in UNSET '' '/' '//' '//foo//' '/tmp//x///' '.' '..' 'relative' '~
         54s bash   cd /home/runner/work/ail-ci/ail-ci && for t in scar_life tally_lang tree_fold; do rm -rf /tmp/gcall/${t}_py_ba
         43s bash   cd /home/runner/work/ail-ci/ail-ci && for p in home2 home3; do for h in UNSET '//foo//' '~' '/tmp//x///'; do e
         20s bash   cd /home/runner/work/ail-ci/ail-ci && for p in env_basic env_direct env_keys env_chain env_containers env_defa
         18s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/gc_head1 /tmp/gc_base1 && mkdir -p /tmp/gc_head1 /tmp/gc_bas

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-01T05:16:35Z
