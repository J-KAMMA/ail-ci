# job job-pre45-10241007  started 2026-10-24T01:08:14Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Fixed the first listed difference: `f = "ab".upper` now fails at compile time (named refusal `C?-job-pre45-10241007-1`) on both builds instead of compiling to a run-time `AttributeError`. `getattr(c, "add")` was already refused by name; `cls.attr` in a classmethod still differs and was left unchanged.

Commit: `09c2e5e` on `job-pre45-10241007` (added `test_ail_pre45.py`, DEVLOG, DIFFERENCES, manifest).

Verification on the final commit:
- `test_ail_pre45` + `test_ail_safetynet` + `test_ail_files` + `test_ail_corpus_findings3`: 27 tests, OK, 1 skipped (no Zig).
- `python3 tools/update_manifest.py --check`: exit 0.
- Probes, both builds:
  - Refused by name: direct/empty/alias/argument/list-item/dict-value/attribute `upper`, plus `str.lower` and `bytes.upper`.
  - Match CPython: fields named `upper`/`lower`/`title`, call-through-attribute, normal str method calls with `key=str.lower`, user-method calls, `int.upper`.
  - Pre-existing unchanged: `cls.attr`, `bytearray.upper`, `bytes.decode`, user-defined method fetched as a value.
  - Residual edge found: if a class field elsewhere shares the name (`upper`) and a string reaches the same unknown-kind parameter, the old run-time failure remains.
[cost $0.0389, opencode tokens {"total": 1455189, "input": 119467, "output": 5548, "reasoning": 22910, "cache.write": 0, "cache.read": 1307264}]
    tool time: bash 10.0 min
        285s bash   cd AIL_CURRENT && python3 -m unittest -v test_ail_safetynet test_ail_files test_ail_corpus_findings3 > /tmp/te
        151s bash   cd AIL_CURRENT && python3 -m unittest -v test_ail_pre45 test_ail_safetynet test_ail_files test_ail_corpus_find
         42s bash   cat > /tmp/probes/bytes_upper_value.py <<'EOF' def main():     b = b"ab"     f = b.upper     print(f())  main(
         32s bash   for p in /tmp/probes/p{1..12}.py; do echo "##### $(basename $p)"; bash ~/tools/cmp.sh "$p" "$PWD" 2>&1 | grep 
         26s bash   cd AIL_CURRENT && python3 -m unittest -v test_ail_pre45 2>&1 | tail -40
         23s bash   for p in /tmp/probes/upper_empty.py /tmp/probes/upper_alias.py /tmp/probes/upper_arg.py /tmp/probes/upper_list
         10s bash   cat > /tmp/probes/str_lower_value.py <<'EOF' f = str.lower print(f("AB")) EOF cat > /tmp/probes/field_named_lo
          8s bash   for p in /tmp/probes/upper_value.py /tmp/probes/getattr_add.py /tmp/probes/cls_attr.py; do echo "##### $p (HEA

## review 0
[model opencode-go/deepseek-v4.1-flash]
**What the change does:** It records every attribute name assigned anywhere via `.name =` (`attr_store_names`, pyboxed2.py:2162) and, on an attribute read whose name is in `_STR_ONLY_METHODS`, refuses when the receiver is statically `str`, or of unknown kind and that name was never stored (pyboxed2.py:5055). Names `self`/`cls` are exempt. It is compile-time only; generated C for programs that get past the check is unchanged.

**Blocking defect: new false refusals.** A class attribute whose name is a str-only method, read through any receiver of unknown static kind (list item, dict value, argument), now fails to compile on the general path and cascades to the default build; both base builds matched CPython.

Probe `/tmp/rprobes/p17_classattr_dict.py`:
```python
class C:
    title = "hi"
def main():
    d = {"k": C()}
    print(d["k"].title)
main()
```
- CPython/base (both builds): `hi`, exit 0.
- HEAD: build fails, `the str method title used as a value ...` (general); default build fails too.

Same regression for `xs[0].title` (p11) and argument `c.format` (p18) with class attributes `title`/`format`; base matched CPython on both builds. `attr_store_names` collects only `ast.Attribute` stores, not class-body assignments, so these are misclassified as str method values. This is a defect caused by the change, not a pre-existing difference and not the task's allowed refusal (these are not str method values).

**Other probes (HEAD vs base):**
- `f = "ab".upper` direct/empty/alias/arg/list-item/dict-value/attribute: refused on both builds with marker (p1–p5). Verified.
- Valid `"ab".upper()`, `str.lower` key, fields stored via `self.title`, class attr via plain name: match CPython both builds (p6, p7, p19, p20).
- `getattr(c, "add")`: same refusal on base/HEAD (p15). `cls.x` in classmethod: same `'type' object has no attribute 'x'` on base/HEAD (p16). `bytearray.upper` value: same run-time `AttributeError` on both (p14).
- p12/p13 (unknown-kind receiver plus an unrelated `.upper`/`.title` store) still produce the old run-time `AttributeError` on HEAD and base: identical on base, listed under Pre-existing; it is the residual hole the report itself discloses.

**Report claims:** direct fix verified; `getattr` claim verified unchanged; `cls.attr` claim verified unchanged; test modules and manifest check verified; the residual edge verified. "No different C for supported programs" verified: `--debug-dir` `program.c` identical to base for g00_000/g00_002 in both builds (only report/log paths differ). Exact "27 tests" count not checked; all four named modules pass.

**Tests:** `par_check.py -j 2 test_ail_pre45 test_ail_safetynet test_ail_files test_ail_corpus_findings3` → 4 modules, 0 failed. `update_manifest.py --check` → 0.

**Pre-existing:** p12/p13 residual str-method-value run-time failures; bytearray.upper; cls.attr in classmethod; os.path.join value (refused on base too).

**Unverified:** instruction counts (not applicable: C unchanged for unaffected programs; affected programs are now refused); full suite (not run, as instructed).

VERDICT: FIX
1. False refusal of valid class attributes named like str methods when reached through a list item, dict value or argument. Probe `/tmp/rprobes/p17_classattr_dict.py` (also p11, p18): expected `hi` / exit 0 as on base and CPython; actual compile refusal `the str method title used as a value ...` on both HEAD builds. Fix by including class-body/annotation names in the store set, or only refusing when the receiver is provably a str.
[cost $0.0197, opencode tokens {"total": 691232, "input": 54263, "output": 4576, "reasoning": 11593, "cache.write": 0, "cache.read": 620800}]
    tool time: bash 5.9 min
        216s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_pre45 test_ail_safetynet test_a
         45s bash   cd /tmp/rprobes; date; for p in p*.py; do echo "##### BASE $p"; bash ~/tools/cmp.sh "$p" /tmp/base 2>&1 | grep
         43s bash   cd /tmp/rprobes; date; for p in p*.py; do echo "##### HEAD $p"; bash ~/tools/cmp.sh "$p" /home/runner/work/ail
         36s bash   cd /tmp/rprobes cat > p15_getattr_add.py <<'EOF' def main():     c = "ab"     print(getattr(c, "add")) main() 
         11s bash   cd /tmp && rm -rf dbg && mkdir -p dbg/h dbg/b for prog in g00_000 g00_002; do  for m in g d; do   if [ "$m" = 
          3s bash   cd /tmp/rprobes && bash ~/tools/cmp.sh p17_classattr_dict.py /home/runner/work/ail-ci/ail-ci 2>&1 | sed -n '1,
          0s bash   git worktree add /tmp/base work >/tmp/wt.log 2>&1; tail -3 /tmp/wt.log; ls /tmp/base/AIL_CURRENT/ail_chatgpt.p
          0s bash   date; pwd; git status --short; git log --oneline -5; echo ---; git log --oneline work..HEAD; echo ---; git dif

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed the review defect and committed `df641dd`.

**Change:** class-body assignment/annotation names (`class C: title = "hi"`, `title: str = "hi"`) now join the attribute-store set, so class attributes named like str methods are no longer refused when reached through a list item, dict value, or argument.

**Probes** (`cmp.sh`, both builds):
- `p01` direct, `p02` empty/alias, `p03` arg/list/dict, `p04` attribute: refused by name with `C?-job-pre45-10241007-1`.
- `p05` valid calls, `p06` field `title`, `p07` user `upper`: match CPython.
- `p08` dict, `p09` list, `p10` argument, `p11` inherited, `p12` annotated, `p13` field `upper`: match CPython on HEAD and base.
- `p14` `getattr(c, "add")`, `p16` bare annotation, `p17` `getattr` class attr: match CPython/base behavior.
- `p15` `cls.x` in classmethod: unchanged pre-existing `'type' object has no attribute 'x'` on both builds.

**Tests:** `par_check.py -j 2 test_ail_pre45 test_ail_safetynet test_ail_files test_ail_corpus_findings3` → 4 modules, 0 failed, 165s. `update_manifest.py --check` → exit 0. Instruction counts not measured; the change only gates a compile-time refusal.
[cost $0.0288, opencode tokens {"total": 1052980, "input": 123271, "output": 5287, "reasoning": 7302, "cache.write": 0, "cache.read": 917120}]
    tool time: bash 4.0 min, edit 0.0 min
        166s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_pre45 test_ail_safetynet test_a
         41s bash   cd /tmp/probes; for p in p0*.py p1[0-5]_*.py; do echo "##### HEAD $p"; bash ~/tools/cmp.sh "$p" /home/runner/w
         22s bash   cd /tmp/probes; for p in p08_classattr_dict.py p09_classattr_list.py p10_classattr_arg.py p11_classattr_inheri
         11s bash   cd /tmp/probes && cat > p16_bare_ann.py <<'EOF' class C:     title: str def main():     d = {"k": C()}     pri
          0s bash   pwd; git status --short; git log --oneline -8; echo ---; git branch -a; echo ---; ls
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 -m py_compile AIL_CURRENT/test_ail_pre45.py AIL_CURRENT/python/p
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c
          0s bash   grep -n "attr_store_names\|_STR_ONLY_METHODS\|str method" AIL_CURRENT/ail_chatgpt.py | head -50

## review 1
[model opencode-go/deepseek-v4.1-flash]
**Review report — `df641dd` / `09c2e5e`**

**What the change does:** adds a compile-time refusal in the general path (`pyboxed2.py:5065`) for `_STR_ONLY_METHODS` attributes read as values when the receiver is `str` or unknown-kind, unless an AST `Attribute` store or class-body name exists anywhere (`pyboxed2.py:2162`). This matches the report.

**Regression found (blocking):** attributes created with builtin `setattr` are not in `attr_store_names`, so valid programs are now refused.

Probe `/tmp/rprobes/r22_user_getattr_store.py`:
```python
class C:
    def __init__(self):
        setattr(self, "title", "hi")

def main():
    d = {"k": C()}
    print(d["k"].title)

main()
```
Expected (CPython, base general **and** default builds): `hi`, exit 0. Actual HEAD: both builds fail with `not in the subset: the str method title used as a value ... C?-job-pre45-10241007-1`. Same regression with `format` (`r30`) and `upper` (`r31`).

**Verified:** direct `f = "ab".upper`, empty, alias-global, list-item and argument variants are now refused by name (previously runtime `AttributeError`); normal calls, `str.lower` as a key, class-body attributes via list/dict/argument/inheritance, `namedtuple`, and fields still match CPython; `getattr(c,"add")` and `cls.x` in a classmethod are unchanged from base. Tests: 4 required modules, 0 failed, 172 s; `update_manifest.py --check` exit 0; `--debug-dir` C for a no-feature program is byte-identical to base.

**Pre-existing:** `r6_bypass_arg` (an unrelated `self.upper = 1` store suppresses the new refusal, leaving the old runtime failure on both HEAD and base), and `cls.x` in a classmethod. These do not block on their own.

**Unverified:** worker’s exact `p16` bare-annotation probe; no gdev instruction counts (compile-time-only change).

VERDICT: FIX
1. `setattr`-created attributes named like str methods are falsely refused. Probe `r22_user_getattr_store.py` (also `r30_setattr_format.py`, `r31_setattr_upper.py`): expected `hi` / `hi` / `hi` exit 0 on both builds (base does this); actual HEAD fails to build with `the str method ... used as a value ... C?-job-pre45-10241007-1`. `attr_store_names` must also collect constant names passed to `setattr`, or the gate must not refuse unknown-kind receivers whose attribute cannot be proven to be a str.
[cost $0.0265, opencode tokens {"total": 977747, "input": 55032, "output": 7540, "reasoning": 18407, "cache.write": 0, "cache.read": 896768}]
    tool time: bash 5.8 min
        173s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_pre45 te
         30s bash   cd /tmp/rprobes; date; for p in r1_direct.py r2_valid_calls.py r6_bypass_arg.py r7_field_unknown.py r10_unrela
         21s bash   cd /tmp/rprobes; date; for p in r17_simplenamespace.py r18_getattr_dynamic.py r19_bytes_upper_value.py r20_ali
         21s bash   cd /tmp/rprobes cat > r23_dict_assign.py <<'EOF' class C:     def __init__(self):         self.__dict__["title
         16s bash   cd /tmp/rprobes; date; for p in r11_str_lower.py r12_namedtuple.py r13_classattr_lower.py r14_func_returns_cla
         16s bash   cd /tmp/rprobes cat > r29_object_setattr_title.py <<'EOF' class C:     def __init__(self):         object.__se
         15s bash   cd /tmp/rprobes; date; for p in r17_simplenamespace.py r18_getattr_dynamic.py r19_bytes_upper_value.py r20_ali
         14s bash   cd /tmp/rprobes; date; for p in r1_direct.py r1b_empty.py r2_valid_calls.py r3_classattr_if.py r4_classattr_tu

FINAL VERDICT: FIX  2026-10-24T01:55:54Z
