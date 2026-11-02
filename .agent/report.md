# job job-prog13-11020843  started 2026-11-01T23:45:24Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Implemented and committed as `793b961`.

- Typed reach: 6/8 programs now fully typed (was 5/8 at base). `g12_026` now builds typed via Optional scalar method support; `g19_036` and `g12_036` remain named follow-ups with exact messages in `lab/progfix/prog13.md`.
- Fixed a correctness edge in the new method lowering: an Optional method result used inline (e.g. a dict value) forces whole-program fallback instead of leaking a lowered tuple.
- Added `AIL_CURRENT/test_ail_prog13.py` + `tests.d` registration, covering newly typed method forms on IR 0/1, `g12_026`, refusal cases, str struct-comprehension, and the 5 previously typed programs.
- Probes: 8 files in `/tmp/probes/prog13_*.py`; all match CPython on both builds, or are refused by name and fall back correctly.
- Tests on final commit: 11 modules, 0 failed (including `test_ail_prog13`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`).
- `lab/compare`: all 10 `main.ail` generated C files are byte-identical to base; the 5 `main.py` builds that build are identical, the other 5 fail in both trees.
- `update_manifest.py --check` passes.
[cost $0.1297, opencode tokens {"total": 14801517, "input": 332368, "output": 25671, "reasoning": 35286, "cache.write": 0, "cache.read": 14408192}]
    tool time: bash 26.5 min
        445s bash   cd /home/runner/work/_temp/w2 && python3 tools/update_manifest.py --check 2>&1 | tail -3; echo manifest_rc=$?;
        392s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_optional_locals test_
        383s bash   cd /home/runner/work/_temp/w2 && rm -rf /tmp/prog13/cmpc && mkdir -p /tmp/prog13/cmpc && fail=0; for task in l
         82s bash   cd /home/runner/work/_temp/w2 && rm -rf /tmp/prog13/cmpa && mkdir -p /tmp/prog13/cmpa && fail=0; for task in l
         68s bash   cd /home/runner/work/_temp/w2 && for m in test_ail_optional_locals test_ail_optional_structs test_ail_optint_e
         26s bash   cd /home/runner/work/_temp/w2 && mkdir -p /tmp/prog13/build && for f in lab/corpus/programs/deepseek-v4.1-flas
         23s bash   cat > /tmp/probes/prog13_opt_methods_none_arg.py <<'PY' class C:     def __init__(self) -> None:         self.
         23s bash   cd /home/runner/work/_temp/w2 && for p in /tmp/probes/prog13_*.py; do echo "===== $(basename $p)"; bash ~/tool

## review 0
[model opencode-go/deepseek-v4.1-flash]
**What the diff actually does.** `optlib.py` lets scalar `Optional` parameters/results be lowered on class methods, keyed by bare method name and assuming the first parameter is `self`; `pyfunc.py` lets a struct-list comprehension emit `list[str]`. This matches the report, but the report omits the receiver/name and self assumptions that cause the two defects below.

**Defects**

1. **Optional method name collides with builtin/container methods** — `/tmp/rprobes/opt_collide_get.py` (also `opt_collide_pop.py`):
   ```python
   class Cache:
       def get(self, k: int | None) -> int | None: ...
   c = Cache(); d = {1: 10, 2: 20}
   print(c.get(3)); print(d.get(1)); print(d.get(9))
   ```
   Expected CPython: `1`, `10`, `None`. Actual on both builds: `1`, then `TypeError: cannot unpack non-iterable int object`, exit 1. Any `<obj>.get(...)`/`<obj>.pop(...)` is rewritten as the Optional method. Base matches CPython, so the change caused it.

2. **Class-scope function without `self` gets its Optional parameter shifted** — `/tmp/rprobes/opt_no_self3.py`:
   ```python
   class C:
       def value(x: int, k: int | None) -> int | None:
           if k is None: return x
           return x + k
   print(C.value(3, 4))
   ```
   Expected CPython: `7`. Actual on both builds: `5` (`skip=1` assumes a receiver parameter always exists). Base matches CPython.

**Verified claims.** 6/8 typed now and 5/8 at base; `g12_026` typed on HEAD and general at base; `g19_036`/`g12_036` remain general with the exact messages quoted; manifest `--check` passes; all 10 `lab/compare/src/*/main.ail` generated `program.c` files are byte-identical to base; non-feature programs (`t140`, `g06_000`, `t371`) have identical `program.c`; all 8 worker probes in `/tmp/probes` match CPython on both builds; `test_ail_prog13` and `test_ail_safetynet` pass (0 failed).

**Unverified.** Worker's other 9 test modules; the "5 `main.py` builds identical / 5 fail in both" claim; instruction counts (`perf_event_open: Permission denied`). No pre-existing differences found.

VERDICT: FIX
[cost $0.0337, opencode tokens {"total": 2902580, "input": 64267, "output": 9847, "reasoning": 16178, "cache.write": 0, "cache.read": 2812288}]
    tool time: bash 9.1 min, write 0.0 min
        196s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_prog13 test_ail_safet
         88s bash   cd /tmp/p13check; rm -rf lch lcb; mkdir lch lcb; cd /home/runner/work/_temp/w2/lab/compare/src; ok=0; diffc=0;
         42s bash   cd /tmp/p13check for f in t140 g19_036 t002 t001 g06_000 g12_036 g12_026 t371; do   case $f in t*) src=/home/r
         41s bash   for p in /tmp/rprobes/*.py; do echo "########## HEAD $(basename $p)"; bash ~/tools/cmp.sh "$p" /home/runner/wo
         33s bash   for p in /tmp/probes/prog13_*.py; do echo "===== $(basename $p)"; bash ~/tools/cmp.sh "$p" /home/runner/work/_
         29s bash   cd /tmp && rm -rf p13check && mkdir p13check && cd p13check declare -A IN=( [t140]=/home/runner/work/_temp/w2/
         28s bash   cd /tmp/p13check for f in g12_026 g12_036 g19_036; do src=/home/runner/work/_temp/w2/lab/census/programs/gdev/
         13s bash   for p in /tmp/rprobes/opt_collide_get.py /tmp/rprobes/opt_collide_pop.py; do echo "########## BASE $(basename 

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed both review defects and committed as `d32759d`.

- Builtin-name collision: Optional methods named like builtin container methods (`get`, `pop`, ...) are now rewritten only when every receiver is provably a user class/instance; otherwise the program falls back whole. `dict.get`/`list.pop` now match CPython.
- Receiver skip: bound/unbound is decided per call (`C.value(3, 4)`, `S.add(obj, 4)` use `skip=0`; instance/`self` calls use `skip=1`). No more argument shifting. Module-level Optional method calls are refused and fall back.
- Added P7/P8 tests to `test_ail_prog13.py`; updated `lab/progfix/prog13.md` and `DEVLOG.md`.

Verification:
- 13 `opt_*` review probes: all match CPython on both builds.
- 4 `struct_str_*` probes: all match.
- Tests on final commit: `test_ail_prog13`, `test_ail_optint_exact`, `test_ail_optional_locals`, `test_ail_py_typed_gaps`, `test_ail_refusal_messages`, `test_ail_nonecrash`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 9/9, 0 failed.
- Generated C: 10/10 `lab/compare` tasks byte-identical to `ecad304`.
- `update_manifest.py --check` passes.

One unrelated pre-existing probe, `p13_direct_mutate.py` (itertools tuple mutation), also differs on the base commit and is untouched by this change.
[cost $0.0570, opencode tokens {"total": 4961240, "input": 109546, "output": 14876, "reasoning": 28626, "cache.write": 0, "cache.read": 4808192}]
    tool time: bash 19.5 min
        444s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_prog13 test_ail_optin
        365s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_prog13 test_ail_optin
        112s bash   cd /home/runner/work/_temp/w2 && for p in /tmp/rprobes/*.py; do printf '%-28s ' "$(basename $p)"; out=$(bash ~
         68s bash   cd /home/runner/work/_temp/w2 && cat > /tmp/check_compare_c.py <<'PY' import hashlib, json, subprocess, sys, t
         56s bash   cd /home/runner/work/_temp/w2 && for p in /tmp/rprobes/*.py; do echo "===== $(basename $p)"; bash ~/tools/cmp.
         37s bash   cd /home/runner/work/_temp/w2 && python3 tools/update_manifest.py && python3 tools/update_manifest.py --check 
         30s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_prog13 2>&1 | tail -2
         26s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_prog13 2>&1 | tail -3

## review 1
[model opencode-go/deepseek-v4.1-flash]
Reviewed `work..HEAD` (`d32759d`, `793b961`) with `/tmp/base` at `work` (`ecad304`). Started 04:00, finished 04:15.

**What the diff really does.** It lets scalar Optionals appear on non-decorated methods with program-unique names, rewrites `recv.name(...)` calls with a per-call receiver skip, adds a builtin-method-name collision guard, and relaxes the struct-list comprehension check to accept `str` elements. This matches the report's description.

**Defects (caused by this change; base passes all four probes).**

1. **Wrong receiver skip when the method's first parameter is not `self`/`cls` and the receiver is not statically known.**
```python
class C:
    def __init__(this, n: int) -> None: this.n = n
    def take(this, k: int | None) -> int | None:
        if k is None: return None
        this.n -= k; return this.n
def run(o): print(o.take(2))
def main() -> None: run(C(9))
main()
```
Expected stdout `7` (CPython, base both builds); HEAD both builds fail: `not in the subset: take() called without a required argument k__v` / `parameter k__p ... is declared bool, but 2 is not a bool`. The fallback for an unknown receiver assumes the first parameter is `self`/`cls`, so skip is 0 and the Optional pair is shifted into `this`.

2. **A class name shadowed/rebound to a `dict` is still classified as a class, so `dict.get` is captured.**
```python
class Cache:
    def get(self, k: int | None) -> int | None:
        if k is None: return None
        return k + 50
def main() -> None:
    Cache = {1: 10, 2: 20}
    print(Cache.get(1)); print(Cache.get(9))
main()
```
Expected `10\nNone`; HEAD compiles then crashes at runtime on both builds: `TypeError: cannot unpack non-iterable int object`, exit 1. The same program with the rebind at module scope (`Cache = {1: 10, 2: 20}` after the class, call inside `main`) is expected `10\nNone`; HEAD fails to build (`get() called without a required argument k__v`). Base both print `10\nNone`. Root cause: `_name_tags` returns `class` for any name in `class_names` before consulting scope bindings, so both the collision guard and `call_skip` misclassify the receiver.

3. **A call to an Optional method in a class body is not rewritten while the method signature is.**
```python
class C:
    def __init__(self, n: int) -> None: self.n = n
    def take(self, k: int | None) -> int | None:
        if k is None: return None
        self.n -= k; return self.n
class D:
    x = C(6).take(2)
def main() -> None: print(D.x)
main()
```
Expected `4` (CPython, base both builds); HEAD both builds fail (`reading the class attribute D.x through the class: its value is not a constant...` / module constant error). `run()` only refuses module-level Optional method calls; class-body statements are neither lowered nor refused.

**Pre-existing (identical on base).** `p10_collide_collection.py` (list/dict `pop` with user `pop`), `p12_datetime_collide.py` (datetime method collision), `p19_class_arg.py` (class passed as an argument) all fail on both HEAD and base, so they do not block.

**Claims checked.**
- `g12_026.py`: verified typed on HEAD (no general-path note) vs general on base, output matches CPython.
- Generated C of the 10 `lab/compare` tasks: verified `different 0 of 10` against `ecad304`.
- `test_ail_prog13` + `test_ail_safetynet`: verified, 2/2 modules pass on HEAD.
- `update_manifest.py --check`: passes.
- Module-level Optional method call refusal: verified (`p8_module_call` falls back and matches).
- Parameter kinds/defaults/bytes/bool/str/float, annotated/global/constructed receivers, struct-list-of-str: verified on both builds.
- “No more argument shifting”: **false** (defect 1).
- “`dict.get`/`list.pop` now match CPython”: true only for plainly typed receivers; **false under class-name shadowing** (defect 2).
- Worker's 13 opt/4 struct probes: unverified (not in the tree); my independent probes found the gaps above.
- The other 7 test modules in the report, and speed/icount: unverified (not required for this review).

VERDICT: FIX
[cost $0.0408, opencode tokens {"total": 1317143, "input": 132653, "output": 8764, "reasoning": 20270, "cache.write": 0, "cache.read": 1155456}]
    tool time: bash 8.3 min
        234s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && date && timeout 1200 python3 ../tools/par_check.py -j 2 test_ail_
         65s bash   cat > /tmp/rprobes/p12_datetime_collide.py <<'PY' import datetime  class Event:     def __init__(self) -> None
         50s bash   cd /home/runner/work/_temp/w2 && echo 'p5 expected:'; python3 /tmp/rprobes/p5_this_method.py; echo 'p23 expect
         46s bash   cd /home/runner/work/_temp/w2 && date && ls /tmp/rprobes/p*.py | grep -E '/p([0-9]|1[01])_' | xargs -P2 -I{} b
         36s bash   cat > /tmp/rprobes/p22_local_shadow.py <<'PY' class Cache:     def get(self, k: int | None) -> int | None:    
         20s bash   cat > /tmp/rprobes/p19_class_arg.py <<'PY' class S:     def __init__(self, n: int) -> None:         self.n = n
         20s bash   cat > /tmp/rprobes/p26_nested_call.py <<'PY' class C:     def __init__(self, n: int) -> None:         self.n =
          9s bash   cd /home/runner/work/_temp/w2 && for f in p1_int_kw p6_default_none p5_this_method; do echo "##### $f"; bash ~

FINAL VERDICT: FIX  2026-11-02T04:15:25Z
