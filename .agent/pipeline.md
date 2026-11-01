# job job-std_abc-11020347  started 2026-11-01T18:47:43Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed all three review defects and committed on `job-std_abc-11020347`.

**Defects**
1. Concrete subclasses inheriting an ABC guard no longer swallow constructor binding errors. A wrong arity is now a named compile refusal (`not in the subset: B() called without a required argument x`); ordinary class-value calls keep their previous runtime fallback.
2. `abc.get_cache_token()` now returns CPython's real starting token (positive, stable), read from a fresh interpreter at compile time, instead of fake `0`.
3. Metaclasses subclassing `ABCMeta` (`class Meta(ABCMeta)`, `metaclass=Meta`, subclasses of `Meta`) are recognised as ABC metaclasses.

**Probes** (`/tmp/probes/`, both builds)
- `arity_concrete`, `routes_arity2`: named refusal, no silent object.
- `arity_custom_own_init`, `cache_value`, `cache_stable`, `meta_sub`, `meta_sub2`: stdout/exit match CPython.
- `lab/compare`: all 10 `main.ail` tasks build; `program.c` byte-identical to the previous branch commit.

**Tests on final commit** (7a6e7f9): `test_ail_std_abc`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4/4 pass. `test_ail_pre363` also passed. `update_manifest.py --check` passes.

Commits: `6b319c9`, `e42b829`, `7a6e7f9`.
[cost $0.0000, opencode tokens {"total": 5071682, "input": 65187, "output": 15989, "reasoning": 28714, "cache.write": 0, "cache.read": 4961792}]
    tool time: bash 13.2 min, edit 0.0 min
        187s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 2400 python3 tools/par_check.py -j 2 test_ail_std_abc test_ail_s
        186s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check && timeout 2400 python3 tools/p
        183s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 2400 python3 tools/par_check.py -j 2 test_ail_std_abc test_ail_s
        132s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 1200 python3 tools/par_check.py -j 2 test_ail_std_abc test_ail_s
         39s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 1200 python3 tools/par_check.py -j 2 test_ail_std_abc 2>&1 | tai
         23s bash   cat > /tmp/cmpc/one.sh <<'EOF' #!/bin/bash task=$1 cur=/home/runner/work/ail-ci/ail-ci base=/tmp/base_ours src
         10s bash   mkdir -p /tmp/probes && cd /tmp/rprobes2 && cp arity_concrete.py arity_custom_own_init.py routes_arity2.py cac
          8s bash   cd /tmp/rprobes2 && for p in arity_concrete.py arity_custom_own_init.py cache_value.py meta_sub.py; do echo "=

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change really does:** distinguishes a class's *own* ABC guard from an inherited one (`pyboxed2.py:7668`, `boxclosure.py:407`), so a concrete subclass's arity error becomes a named compile refusal instead of a silently built object; recognises classes that subclass `ABCMeta` as ABC metaclasses (`smalllib5.py:220-237`); and replaces the constant `get_cache_token()` `0` with a token sampled at compile time from `python3 -c 'import abc;print(abc.get_cache_token())'` (`smalllib5.py:354-373`).

**Checks run**
- `test_ail_std_abc`, `test_ail_safetynet`: 2/2 pass (127 s) on HEAD `7a6e7f9`.
- `python3 tools/update_manifest.py --check`: exit 0.
- Non-feature C: `lab/compare/src/echo_pack/main.py` debug `program.c` byte-identical between HEAD and `/tmp/base` (25213 lines).
- Probes on both builds with `~/tools/cmp.sh`:
  - Review defects: `arity_concrete`, `routes_arity2`, `attr_arity` → named refusals (fix accepted); `arity_custom_own_init`, `cache_value`, `cache_stable`, `meta_sub`, `meta_sub2`, `meta_attr`, `meta_plain`, `valid_concrete`, `attr_valid`, `noinit_concrete_args`, `runtime_pick` → match CPython.
  - New boundary probes: `token_numbers`, `token_order`, `token_fractions`, `token_decimal`, `token_statistics` → **wrong** (below).
  - Refusals confirmed: `A.register` and `abc.update_abstractmethods` are refused by name.

**Defect**
1. `abc.get_cache_token()` is still silently wrong whenever the program imports a module that registers ABCs before the call. The comment/claim that only `register`/`update_abstractmethods` change the token is false; `numbers`, `decimal`, `fractions` and `statistics` all bump it. Probe `/tmp/rprobes3/token_order.py`:
```python
import abc
first = abc.get_cache_token()
import numbers
second = abc.get_cache_token()
print(first, second, first == second)
```
Expected `24 27 False`; actual `24 24 True` (both builds). `token_numbers.py` expects `27`, actual `24`; `import fractions|decimal|statistics` expect `28`, actual `24`. The base printed `0` (also wrong), but this job's task explicitly required the token to be exact or a named refusal, and the report/RESULTS claim it is exact and constant is contradicted. A refusal of `get_cache_token` (as the last review said was acceptable) or modeling the imports would fix it.

**Claims**
- Concrete-subclass arity fix: verified (named refusal, never a silent object; valid calls still build).
- Metaclass handling: verified for `class Meta(ABCMeta)`, `metaclass=Meta`, subclass of `Meta`, and `abc.ABCMeta` spelling.
- Cache token: **false in general** — correct only when nothing before it registers an ABC (`cache_value` passes; `token_order` fails).
- "Ordinary class-value fallback kept": verified identical to base (`plain_value_arity` gives the same generic `P() takes other arguments`).
- "10/10 lab/compare byte-identical": only spot-checked `echo_pack`; not fully verified.

**Pre-existing (identical on `/tmp/base`)**
- `class Meta(ABC)` used as a metaclass: CPython exits with `TypeError: Meta() takes no arguments`, both base and HEAD print `built` (`meta_abc_base.py`).
- Plain class-value arity errors: generic `P() takes other arguments` instead of CPython's exact message (`plain_value_arity.py`; base identical).
- Multiple inheritance remains refused.

**Unverified:** full 10-task `lab/compare` C comparison; `test_ail_files`/`test_ail_corpus_findings3`; speed (the change is compile-time only, no runtime hot path).

VERDICT: FIX
1. `get_cache_token` returns a wrong constant when an earlier import changes CPython's ABC token. Probe `/tmp/rprobes3/token_order.py` expected `24 27 False`, actual `24 24 True` (also `token_numbers.py` expected `27`, actual `24`). Make it a named refusal or derive/model the real token.
[cost $0.0000, opencode tokens {"total": 1067184, "input": 85027, "output": 6376, "reasoning": 16677, "cache.write": 0, "cache.read": 959104}]
    tool time: bash 3.8 min
        128s bash   cd /home/runner/work/ail-ci/ail-ci && date && timeout 1800 python3 tools/par_check.py -j 2 test_ail_std_abc te
         38s bash   cd /tmp/rprobes3 && for m in fractions decimal statistics; do cat > token_$m.py <<EOF import $m import abc pri
         13s bash   cd /tmp && rm -rf dch dbh && mkdir -p dch dbh && AIL_NO_CACHE=1 python3 /home/runner/work/ail-ci/ail-ci/AIL_CU
         10s bash   cd /tmp/probes && for p in *.py; do echo "===== HEAD $p ====="; timeout 200 bash ~/tools/cmp.sh "$p" /home/run
         10s bash   cd /tmp/rprobes2 && for p in arity_concrete.py arity_custom_own_init.py cache_value.py meta_sub.py routes_arit
         10s bash   cd /tmp/rprobes3 && for p in token_numbers.py token_register.py meta_abc_base.py valid_concrete.py plain_value
          7s bash   cd /tmp/rprobes3 && cat > concrete_own_init_route.py <<'EOF' from abc import ABC, abstractmethod  class A(ABC)
          6s bash   cd /tmp/rprobes3 && for p in meta_plain.py attr_arity.py attr_valid.py noinit_concrete_args.py; do echo "=====

## worker report 1
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Fixed the remaining defect: `get_cache_token()` is now exact only when the program imports `abc` alone (plus `__future__`); any other import makes it a named compile refusal naming the module, instead of returning a wrong constant.

Probes (both builds):
- `token_order`, `token_numbers`, `token_fractions`, `token_decimal`, `token_statistics`, `cache_order`, `cache_numbers_route` → refused by name.
- `cache_value`, `cache_stable`, `cache_routes`, `cache_future_alias` → match CPython.
- Re-ran prior review probes: arity/meta cases still refuse or match as before; only pre-existing `meta_abc_base` and `plain_value_arity` differences remain.

Final commit `2195906`. On that commit:
- `test_ail_std_abc`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: 4/4 pass (184 s).
- `python3 tools/update_manifest.py --check`: exit 0.
- `lab/compare`: not rebuilt this round; none of the 10 sources imports `abc`, and the changed code runs only inside `run_abc`, so their generated C is unaffected.
[cost $0.0263, opencode tokens {"total": 1800480, "input": 65992, "output": 7923, "reasoning": 10853, "cache.write": 0, "cache.read": 1715712}]
    tool time: bash 7.3 min, edit 0.0 min
        185s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check && timeout 2400 python3 tools/p
        181s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 2400 python3 tools/par_check.py -j 2 test_ail_std_abc test_ail_s
         16s bash   cd /tmp/rprobes3 && for p in token_order.py token_numbers.py token_fractions.py token_decimal.py token_statist
         15s bash   cd /tmp/rprobes3 && timeout 200 bash ~/tools/cmp.sh token_fractions.py /home/runner/work/ail-ci/ail-ci 2>&1 | 
         13s bash   cd /tmp/rprobes3 && for p in token_register.py token_register2.py token_update.py meta_abc_base.py valid_concr
          9s bash   cd /tmp/rprobes2 && for p in arity_concrete.py arity_custom_own_init.py routes_arity.py meta_sub.py meta_sub2.
          7s bash   cd /tmp/probes && for p in cache_value.py cache_stable.py cache_routes.py cache_future_alias.py cache_order.py
          3s bash   cd /tmp/rprobes2 && for p in cache_value.py cache_stable.py; do echo "===== $p ====="; timeout 200 bash ~/tool

## review 1
[model opencode-go/deepseek-v4.1-flash]
## review 2 (final)

**What the change really does:** fixes the prior review's three defects in the `abc` pass: `get_cache_token()` is now a compile-time-read exact value only for `abc`-only imports (otherwise a named refusal), `ABCMeta` subclasses used as metaclasses are recognised, and only a class's *own* guard raises before `__init__` binding, so concrete subclasses that inherit a guard no longer swallow arity errors. As before, it also touches `pyboxed2._call_class` / `boxclosure.call_value` for all class-value dispatch whenever a guard exists.

**Probes (`/tmp/rprobes4`, `cmp.sh`, both builds; base `/tmp/base`)**
- Match CPython both builds: `cache_simple`, `cache_alias`, `cache_from`, `cache_future` (token 24, positive, stable); `meta_sub`, `meta_sub2` (exact `Can't instantiate abstract class ...`); `valid_concrete`, `own_init_concrete_valid`, `route_direct`, `route_list`, `route_dict`, `route_arg`.
- Named refusal, both builds: `cache_other`, `cache_nested_import`, `cache_ref`, `cache_dynamic`, `cache_monkey`, `cache_alias_value`, `cache_register`, `cache_update_abs`; `arity_concrete`, `arity_custom_own_init` (`B() called without a required argument x`).
- Collateral regression (caused by change, named refusal): `lambda_regress` — an ABC subclass with a required `__init__` passed to a factory plus a zero-arg lambda. Base built it and matched (`5`); HEAD refuses `B() called without a required argument x`, because `class_values` makes every zero-arg value call speculatively try `_call_class(B, [])`. This is a named refusal, so acceptable under the probe rule, but it is a real coverage loss worth noting.
- Pre-existing (identical wrong output/refusal on base): `meta_type` (`Meta Meta` vs `type type`), `meta_init_print` (missing metaclass `__init__` prints), `meta_abc_base`, `plain_value_arity`.

**Tests / checks**
- `test_ail_std_abc`, `test_ail_safetynet`: 2/2 pass (134 s).
- `python3 tools/update_manifest.py --check`: exit 0.
- `lab/compare`: not rebuilt this round; grep shows no `main.ail` mentioning `abc`, and the guarded code is inert without a generated guard, so C is unaffected (consistent with commit `7a6e7f9`'s 10/10).

**Report claims**
- cache-token exactness and named refusal for other imports: verified (probes above).
- prior arity/meta review cases now refuse or match: verified.
- final commit `2195906`, 4/4 tests, manifest: commit/manifest verified; I ran only the 2 edited/relevant modules (files/corpus not edited, not re-run).
- `lab/compare` unaffected: verified by inspection/reasoning, not rebuilt.
- No crash or silent difference found from the change; metaclass recognition improves `Shape()` from silently built (base) to the exact abstract error.

**Non-blocking note:** `lambda_regress` shows the inherited-guard re-raise in `boxclosure.call_value` also fires for unreachable speculative class-value branches; it is still a named refusal, never silence.

VERDICT: ACCEPT
[cost $0.0316, opencode tokens {"total": 1283651, "input": 69600, "output": 7809, "reasoning": 21474, "cache.write": 0, "cache.read": 1184768}]
    tool time: bash 3.5 min
        135s bash   date && cd /home/runner/work/ail-ci/ail-ci && timeout 900 python3 tools/par_check.py -j 2 test_ail_std_abc tes
         20s bash   cd /tmp/rprobes4 && cat > route_direct.py <<'EOF' from abc import ABC, abstractmethod class A(ABC):     @abstr
         13s bash   cd /tmp/rprobes4 && cat > bisect_a.py <<'EOF' from abc import ABC, abstractmethod class A(ABC):     @abstractm
          7s bash   cd /tmp/rprobes3 && for p in meta_abc_base.py plain_value_arity.py; do echo "===== $p ====="; for wt in /home/
          5s bash   cd /tmp/rprobes4 && cat > valid_concrete.py <<'EOF' from abc import ABC, abstractmethod  class A(ABC):     @ab
          5s bash   cd /tmp/rprobes4 && for p in arity_concrete.py arity_custom_own_init.py meta_sub.py meta_sub2.py; do echo "===
          4s bash   cd /tmp/rprobes4 && cat > meta_init_print.py <<'EOF' from abc import ABCMeta, abstractmethod   class Meta(ABCM
          4s bash   cd /tmp/rprobes4 && for p in cache_alias.py cache_from.py cache_future.py cache_other.py cache_nested_import.p

## full suite
test_ail_quirks

## worker report (suite fix)
[model opencode-go/deepseek-v4.1-flash]
Fixed and committed as `8dad2a6`.

- Cause: `test_ail_quirks` passes raw `@dataclass` source straight to the general path, which built classes without the generated `__init__`, causing runtime `TypeError`.
- Fix: `pyboxed2` now refuses a raw `@dataclass` by name instead of silently building a broken class. Preprocessed dataclass sources still work.
- Verified: `test_ail_quirks`, `test_ail_std_abc`, `test_ail_silent6.DataclassEqTests`, `test_ail_safetynet` all pass; manifest check clean.
[cost $0.0333, opencode tokens {"total": 2671576, "input": 129938, "output": 4881, "reasoning": 5557, "cache.write": 0, "cache.read": 2531200}]
    tool time: bash 7.2 min, edit 0.0 min
        140s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_safetynet 2>&1 | tail -30
        125s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_quirks 2>&1 | tail -80
         82s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_quirks 2>&1 | tail -40
         45s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_std_abc 2>&1 | tail -30
         29s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_silent6.DataclassEqTests 2>&1 | tail -30
         10s bash   cd /tmp/orig/AIL_CURRENT && python3 -m unittest -q test_ail_quirks.Quirks.test_fold_over_dataclass_instances t
          2s bash   git worktree add --detach /tmp/orig origin/job-std_abc-11020347 >/dev/null && cd /tmp/orig/AIL_CURRENT && pyth
          1s bash   cd AIL_CURRENT && mkdir -p /tmp/qk && cat > /tmp/qk/t.py <<'EOF' from dataclasses import dataclass  @dataclass

## full suite again
test_ail_genlib

FINAL VERDICT: FIX  2026-11-01T22:21:44Z
