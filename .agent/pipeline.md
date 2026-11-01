# job job-std_string-11011434  started 2026-11-01T05:37:09Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done on branch `job-std_string-11011434` (commits `65a531c`, `84c9013`).

- Added 12 programs + `RESULTS.md` under `lab/stdlib/string/`.
- Final: **11/12 build** (2 typed, 9 general), all matching CPython stdout/exit code on default and forced-general paths. `formatter_table.py` remains refused: `string.Formatter() ... is not built`.
- Fixed `string.capwords(s=..., sep=...)` and added `string.Template` support (`substitute`, `safe_substitute`, `is_valid`, `get_identifiers`, `template`, `$name`/`${name}`/`$$`, CPython KeyError/ValueError text). Template used as a plain value and Template subclasses are refused by name.
- Added `test_ail_std_string.py` via `tests.d`; updated `test_ail_stdlib1.py`.
- Tests: `test_ail_std_string`, `test_ail_stdlib1`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — **5 modules, 0 failed**. `update_manifest.py --check` passes.
- Generated C of all 10 `lab/compare` tasks is byte-identical.
- Probes (both builds): `p_const`, `p_capwords_edges`, `p_template`, `p_template_edges`, `p_template_values` all match CPython; `p_template_value` and `p_formatter` are refused by name.
[cost $0.0000, opencode tokens {"total": 11007332, "input": 92400, "output": 28830, "reasoning": 43094, "cache.write": 0, "cache.read": 10843008}]
    tool time: bash 29.4 min
        540s bash   python3 tools/par_check.py -j 2 test_ail_std_string test_ail_stdlib1 test_ail_safetynet test_ail_files test_ai
        496s bash   git add AIL_CURRENT/manifest.d/e0.txt && python3 tools/par_check.py -j 2 test_ail_std_string test_ail_stdlib1 
        120s bash   for src in lab/stdlib/string/*.py; do name=$(basename "$src" .py); echo "=== $name ==="; bash ~/tools/cmp.sh "
         67s bash   for p in p_template p_template_edges p_template_values p_const p_capwords_edges; do echo "=== $p ==="; bash ~/
         61s bash   for src in lab/stdlib/string/*.py; do name=$(basename "$src" .py); d=$(mktemp -d); cp "$src" "$d/$name.py"; (c
         58s bash   bash /tmp/probes/run_lab.sh "$PWD" 2>&1 | tee /tmp/probes/lab_after4.txt
         50s bash   bash /tmp/probes/run_lab.sh "$PWD" 2>&1 | tee /tmp/probes/lab_after3.txt
         50s bash   bash /tmp/probes/run_lab.sh "$PWD" 2>&1 | tee /tmp/probes/lab_after2.txt

## review 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Review complete on HEAD (`84c9013`), base `work` (`664cb30`) in `/tmp/base`.

**What the change really does:** `ail_syntax.py` accepts `string.capwords` keyword arguments (`s=`, `sep=`) and lowers `string.Template(...)` plus direct calls to `substitute` / `safe_substitute` / `is_valid` / `get_identifiers` to a prelude object `_AilStringTemplate` and `_ail_tpl_*` helpers. The methods are compile-time rewrites, not actual methods on the object. It also adds the 12 lab programs, `RESULTS.md`, `test_ail_std_string.py`, and the manifest entries.

**Probes (both default and `AIL_UNIFIED_FORCE=1`):**
- `r_plain` (constants/capwords positional): same as CPython.
- `r_cap_ctx` (keywords, empty/None/bytes/int seps, argument/list/dict/attribute values): same as CPython, including the `AttributeError` vs `TypeError` split.
- `r_fromimp`, `r_tpl_inline`, `r_tpl_ctx`, `r_tpl_iter`: same.
- `r_tpl_edges` + `r_tpl_fuzz` (59 templates: `$$`, invalid forms, line/col across `\n`/`\r`, unicode, empty, missing keys, keyword precedence, non-str templates): same except the `bytes` case below and the bound-method case below.
- `r_cap_dup`, `r_tpl_star` (`**kwargs`), `p_tpl_class` (Template subclass): named compile-time refusal, acceptable.
- `r_tpl_value`, `r_tpl_bytes2`: **build succeeds and the program crashes** (defects).

**Claims checked:** 12 programs + RESULTS present (verified); 11/12 build and match CPython (verified by `test_ail_std_string`); capwords keywords and Template support (verified); Template-valued use/subclass refused by name (verified; subclass refusal is `a non-name base class in class MyTemplate`); tests `test_ail_std_string`, `test_ail_stdlib1`, `test_ail_safetynet` pass (248 s, 0 failed); `update_manifest.py --check` passes; compare-task C is identical for the five tasks that build (`berth_sim`, `echo_pack`, `ledger_bin`, `term_rank`, `ticket_audit`).

**Defects:**
1. Template methods only exist as compile-time call rewrites, so referencing one as a value builds and crashes.
   Probe `/tmp/rprobes/r_tpl_value.py`:
   ```python
   import string
   t = string.Template("$x ${y}")
   f = t.substitute
   print(f({"x": 1, "y": 2}))
   g = t.get_identifiers
   print(g())
   ```
   Expected (CPython): stdout `1 2` and `['x', 'y']`, exit 0. Actual: build exit 0, run exit 1, no stdout, `AttributeError: '_AilStringTemplate' object has no attribute 'substitute'`. The base refused this program by name, so the change caused the crash. (`getattr(t, "substitute")` and `getattr(t, "is_valid")()` fail the same way.)
2. Wrong TypeError text for a bytes template, on both builds.
   Probe `/tmp/rprobes/r_tpl_badtext.py`:
   ```python
   import string
   try: string.Template(b"$x").substitute({})
   except Exception as exc: print(type(exc).__name__, exc)
   ```
   Expected: `TypeError cannot use a string pattern on a bytes-like object`. Actual: `TypeError expected string or bytes-like object, got 'bytes'`. (int, None and list templates match CPython.)

**Pre-existing:** `chain_relax`, `rail_transfer`, `scar_life`, `tally_lang`, `tree_fold` fail identically on base (re/typing limitations); not caused by this change.

**Unverified:** instruction-count speed (runtime code for non-Template programs is unchanged, so not measured); typed/general counts per program not independently audited; the five compare tasks that emit no C were only checked for identical failure.

VERDICT: FIX
1. Template method used as a value (`f = t.substitute`) compiles but crashes; expected CPython output `1 2` / `['x', 'y']`, actual `AttributeError: '_AilStringTemplate' object has no attribute 'substitute'` (probe `/tmp/rprobes/r_tpl_value.py`).
2. Bytes-template error message differs; expected `TypeError cannot use a string pattern on a bytes-like object`, actual `TypeError expected string or bytes-like object, got 'bytes'` (probe `/tmp/rprobes/r_tpl_badtext.py`).
[cost $0.0487, opencode tokens {"total": 2505741, "input": 104728, "output": 8922, "reasoning": 34203, "cache.write": 0, "cache.read": 2357888}]
    tool time: bash 21.9 min
        522s bash   date; cd /home/runner/work/_temp/w2 && for t in $(ls lab/compare/src); do rm -rf /tmp/dh /tmp/db /tmp/oh /tmp/
        249s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_std_string te
        196s bash   cd /home/runner/work/_temp/w2 && for t in echo_pack tally_lang ticket_audit; do echo "== $t"; rm -rf /tmp/dh /
         70s bash   cd /tmp/rprobes && python3 - <<'EOF' p='r_cap_ctx.py' s=open(p).read() s=s.split('try:\n    print(string.capwo
         69s bash   date; cd /home/runner/work/_temp/w2 && for t in $(ls lab/compare/src); do rm -rf /tmp/dh /tmp/db; AIL_NO_CACHE
         59s bash   cd /home/runner/work/_temp/w2 && for p in r_plain r_tpl_edges r_cap_ctx r_tpl_ctx r_dup_s; do echo "######## $
         37s bash   cd /home/runner/work/_temp/w2 && rm -rf /tmp/dbg_head /tmp/dbg_base /tmp/o_head.c /tmp/o_base.c && AIL_NO_CACH
         25s bash   date; cat > /tmp/rprobes/r_tpl_badtext.py <<'EOF' import string for tpl in (b"$x", 5, None, ["$x"]):     t = s

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed both defects in commit `57b9ebc`.

- **Method-as-value crash:** Template methods now exist on the prelude object, so `getattr(t, "substitute")(...)` works. Reading a method as a value (`f = t.substitute`, `f = t.get_identifiers`, `getattr(t, "substitute")` as a value) is refused by name instead of crashing. Bound-method values are documented as a follow-up in `RESULTS.md`.
- **Bytes-template message:** bytes and bytearray templates now raise CPython's exact `TypeError: cannot use a string pattern on a bytes-like object`; other non-str types keep their existing messages.

**Probes** (`cmp.sh`, default + `AIL_UNIFIED_FORCE=1`):
- `p_tpl_value`, `p_tpl_value2`, `p_tpl_value_fromimp` — refused by name.
- `p_tpl_getattr_value` — refused by name.
- `p_tpl_getattr_call`, `p_tpl_methods_all`, `p_tpl_badtext_direct`, `p_tpl_badtext_fromimp`, `p_tpl_edges_extra` — same stdout/exit as CPython.

**Verification on HEAD:**
- `test_ail_std_string`, `test_ail_stdlib1`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: 5 modules, 0 failed (538 s).
- `update_manifest.py --check`: passes.
- Generated C for all 10 `lab/compare` tasks: byte-identical.
[cost $0.0519, opencode tokens {"total": 4244397, "input": 113475, "output": 14463, "reasoning": 23275, "cache.write": 0, "cache.read": 4093184}]
    tool time: bash 23.6 min, read 0.0 min
        539s bash   cd /home/runner/work/_temp/w2 && python3 tools/update_manifest.py --check && echo MANIFEST_OK && date && pytho
        519s bash   cd /home/runner/work/_temp/w2 && date && python3 tools/par_check.py -j 2 test_ail_std_string test_ail_stdlib1 
        114s bash   cd /home/runner/work/_temp/w2 && for p in p_tpl_value p_tpl_value2 p_tpl_getattr_value p_tpl_value_fromimp p_t
         41s bash   cd /home/runner/work/_temp/w2 && python3 /tmp/check_codegen.py 2>&1 | tail -20
         40s bash   cd /home/runner/work/_temp/w2 && python3 - <<'PY' p='AIL_CURRENT/ail_syntax.py' s=open(p).read() old="""def _a
         23s bash   cat > /tmp/probes/p_tpl_badtext_direct.py <<'EOF' import string  for tpl in (b"$x", bytearray(b"$x"), 5, None,
         23s bash   cat > /tmp/probes/p_tpl_value_fromimp.py <<'EOF' from string import Template  t = Template("$x ${y}") f = t.su
         22s bash   cat > /tmp/probes/p_tpl_methods_all.py <<'EOF' import string  LITERAL = "$x ${y}"   def render(t, mapping):   

## review 1
[model opencode-go/deepseek-v4.1-flash]
## Review

**Change:** adds a `string.Template` prelude lowering (substitute / safe_substitute / is_valid / get_identifiers, `$$`/`$name`/`${name}`, named refusals for class- and method-as-value, CPython's bytes TypeError), widens `capwords()` to `s=`/`sep=` keywords, and adds the 12 lab programs, `RESULTS.md`, `test_ail_std_string`, DEVLOG and manifest entries.

**Probes** (`bash ~/tools/cmp.sh`, default + `AIL_UNIFIED_FORCE=1`):
- pass: `p2_tpl_types`, `p2_tpl_invalid`, `p2_cap_kw`, `p2_cap_edge`, `p_tpl_basic`, `p_tpl_alias`, `p4_attr_only`, `p4_values_dollar`, `p5_ids`, `p5_dupkw`, `p6_empty`, `p6_unicode`, `p6_cap_bytes`, `p7_ctx`.
- refused by name: method values (`p3_method_value_attr`, `p6_getattr_value`), class value (`p3_class_value`), subclass (`p3_subclass`), `isinstance(t, string.Template)` (`p4_type`), `t.substitute(**m)` (`p4_star`).
- **crash**: `p8_setattr`, `p9_lambda_method` (below).

**Defect**
1. `_Surface.call` (ail_syntax.py:2493-2496) lowers **every** `.substitute/.safe_substitute/.is_valid/.get_identifiers` call once any `string.Template` appears anywhere, without checking the receiver. An unrelated receiver is miscompiled into the Template helper and crashes.
   `p8_setattr.py`:
   ```python
   import string
   class Box: pass
   def check(): return "BOX"
   def main():
       t = string.Template("$x")
       print(t.substitute(x=1))
       b = Box(); setattr(b, "is_valid", check)
       print(b.is_valid())
   main()
   ```
   Expected (CPython, exit 0): `1` then `BOX`.
   Actual (both builds, exit 1): `1` then `AttributeError: 'Box' object has no attribute 'template'`.
   The identical program without the Template (`p9_setattr_only.py`, printing only `BOX`) builds and matches on *both* base and HEAD, so the new gate is what turns it into a crash. `p9_lambda_method.py` (an unrelated class attribute `is_valid = lambda self: "BOX"`, elsewhere a named refusal on base) likewise compiles and crashes instead of refusing.
   Same root cause, smaller effect: `p7_dataclass_flag.py` (a dataclass field named `is_valid`) and `p3_collision.py` are wrongly refused as `string.Template.is_valid used as a value`; these are named refusals, so not blocking by themselves.

**Claims**
- Method-as-value refused by name / `getattr(t,"substitute")(...)` works: verified.
- bytes/bytearray exact `cannot use a string pattern on a bytes-like object`; other non-str messages unchanged: verified (`p2_tpl_types`).
- 11/12 lab programs match CPython on both builds: verified (`test_ail_std_string` passes).
- 10 `lab/compare` C byte-identical: verified (translate+to_c, all 10 same).
- `update_manifest.py --check`: verified.
- 5 test modules, 0 failed: `test_ail_std_string`, `test_ail_stdlib1`, `test_ail_safetynet` re-run, 0 failed (333 s); `test_ail_files` and `test_ail_corpus_findings3` not re-run.

**Pre-existing:** `getattr(obj, name)()` with a non-literal method name crashes identically on base (`p_getattr_class`), so the Template variants of that are not caused here. `capwords`/Template named refusals are acceptable.

**Unverified:** the two remaining required modules; the “6 built before the fix” count; speed (no hot runtime path touched).

VERDICT: FIX
1. Restrict the Template-method lowering to receivers actually known to be Templates (or refuse when not), so unrelated `.is_valid()` / `.substitute()` calls are not hijacked; currently `p8_setattr.py` prints `1\nBOX` (exit 0) on CPython but prints `1\n` then `AttributeError: 'Box' object has no attribute 'template'` (exit 1) on both AIL builds.
[cost $0.0458, opencode tokens {"total": 1840732, "input": 90984, "output": 10094, "reasoning": 34950, "cache.write": 0, "cache.read": 1704704}]
    tool time: bash 19.4 min
        334s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_std_string te
        120s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && date && nohup python3 ../tools/par_check.py -j 2 test_ail_std_str
        102s bash   cd /home/runner/work/_temp/w2 && date && for p in p_cap_kw p_tpl_basic p_tpl_types p_tpl_alias p_tpl_invalid; 
        100s bash   cat > /tmp/rprobes/p6_empty.py <<'EOF' import string  def main():     for text in ("", " ", "$$", "$x", "no pl
         97s bash   cat > /tmp/rprobes/p5_typename.py <<'EOF' import string  def main():     t = string.Template("$x")     print(t
         95s bash   cd /home/runner/work/_temp/w2 && date && for p in p2_tpl_types p2_tpl_invalid p2_cap_kw p2_cap_edge; do echo "
         93s bash   cd /home/runner/work/_temp/w2 && date && for p in p4_type p4_attr_only p4_star p4_values_dollar p4_errors; do 
         41s bash   cat > /tmp/rprobes/p8_alias_method.py <<'EOF' import string  class Box:     def is_valid_impl(self):         r

FINAL VERDICT: FIX  2026-11-01T07:51:11Z
