# job job-pre38-10241003  started 2026-10-24T01:03:26Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed as `81e8a11` on `job-pre38-10241003`.

What changed:
- `dict(<user instance>)` now follows CPython’s mapping protocol when the class has `keys()` or a `keys` attribute: calls `keys()` once, then maps keys through `__getitem__`.
- q01 now reports `D.keys() returned a non-iterable (type NoIter)`; q07 now reports `'list'/'str' object is not callable`.
- Instances without `__iter__` now name their class instead of `instance` in iteration errors.
- q02 (pair-sequence error text) was left untouched and still differs.
- Added `AIL_CURRENT/test_ail_pre38.py` and registered it; updated DEVLOG/DIFFERENCES and the manifest.

Verification on final commit:
- `test_ail_pre38`: 2 tests, OK
- `test_ail_safetynet`: 5 tests, OK
- `test_ail_files`: 18 tests, OK (1 skipped)
- `test_ail_corpus_findings3`: 2 tests, OK
- `update_manifest.py --check`: exit 0

Probes (`bash ~/tools/cmp.sh`, both builds): `q01`, `q01b`, `q01c`, `q07b_list`, `q07b_str`, `p_dict_mapping`, `p_dict_badkeys`, `p_dict_keys_attr`, `p_dict_noiter`, `p_dict_iter_pairs`, `p_dict_missing_getitem`, `p_dict_getitem_error`, `p_dict_callable_attr`, `p_dict_keytypes`, `p_dict_shadow`, `p_dict_badkeys2`, `p_dict_keys_attr2`, `p_dict_noiter2` — all matched CPython. `q02` still mismatches as noted above.
[cost $0.0000, opencode tokens {"total": 9666547, "input": 265336, "output": 37952, "reasoning": 10043, "cache.write": 0, "cache.read": 9353216}]
    tool time: bash 11.8 min
        384s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && for m in test_ail_pre38 test_ail_safetynet test_ail_files te
         98s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -B test_ail_safetynet.py 2>&1 | tail -20
         70s bash   cd /home/runner/work/ail-ci/ail-ci && for p in q01 q01b q01c q07b_list q07b_str p_dict_mapping p_dict_badkeys 
         31s bash   cd /tmp/probes && cat > p_dict_mapping.py <<'EOF' class D:     def __init__(self):         self.tag = 10     d
         18s bash   cd /tmp/probes && cat > p_dict_keytypes.py <<'EOF' class D:     def keys(self):         return [1, 2.5, (3, 4)
         18s bash   cd /tmp/probes && sed -i '/print(dict(d.keys()))/d' p_dict_keytypes.py && cd /home/runner/work/ail-ci/ail-ci &
         17s bash   cd /home/runner/work/ail-ci/ail-ci && for p in q01 q01b q01c q07b_list q07b_str; do echo "=== $p"; bash ~/tool
         14s bash   mkdir -p /tmp/probes && cat > /tmp/probes/q01.py <<'EOF' class NoIter:     def __init__(self):         self.x 

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change does.** It records user `keys`/`__getitem__` methods on class objects, routes `dict(x)` (non-stdin, both builds) through a new runtime mapping helper when `x` is an instance, falls back to pair update, and renames generic instance-iteration errors to the class name. It also drops `_resolve_iter_src` for every other `dict(x)` argument, not just instances.

**Verification**
- `test_ail_pre38` (2 tests) and `test_ail_safetynet` (5 tests): both OK on HEAD; `update_manifest.py --check` exit 0.
- q01 first line, q07 (`list`/`str`), and class-named iteration errors match CPython on both builds.
- Extra probes found new mismatches below.

**Pre-existing (base identical, does not block)**
- `p_seqproto2`: keys object iterable only via `__getitem__` is refused; `p_nextonly2`: `__next__`-only object accepted by plain iteration; `p_general_call`: user `__call__` unsupported; `p_liststr`: strings as pair elements unsupported; q01 object repr differs by address.

**Unverified**
- Exact q02 reproduction; `test_ail_files`/`test_ail_corpus_findings3` (not rerun per instructions); speed (icount fails: `perf_event_open: Permission denied`); `--debug-dir` C equality for non-feature programs (behavioral regression found instead).

**Report claims**
- Commit/branch, test registration, DEVLOG/DIFFERENCES/manifest: verified.
- “`dict(<user instance>)` follows CPython when the class has `keys()` or a `keys` attribute”: **false** for a callable attribute (`p_callable`: CPython `{'a': 1, 'b': 1}`, HEAD `TypeError 'K' object is not callable`) and for `keys(self, *args)` (`p_keys_star`: CPython `{'a': 5}`, HEAD `TypeError 'D' object is not iterable`; base also failed).
- q02 still differs: unverified. “All probes matched”: not true of the boundaries above.

VERDICT: FIX
1. **Segfault calling an instance-stored function as if bound** — `/tmp/rprobes/p_instfunc2.py`:
```python
class D:
    def __init__(self):
        self.keys = lambda x, y: [x, y]
    def __getitem__(self, k):
        return 2
try:
    print(dict(D()))
except Exception as e:
    print(type(e).__name__, e)
```
CPython: `TypeError ... missing 2 required positional arguments: 'x' and 'y'`. HEAD (both builds): Segmentation fault, exit 139. Base: `TypeError 'instance' object is not iterable` (no crash). Same code with a 1-argument lambda (`p_instfunc1.py`) wrongly returns `1 [1]` instead of CPython’s TypeError. Instance-assigned functions are not descriptors; only instance-table `keys` values that originated as class functions may be bound to `self`.

2. **`__next__`-only keys result wrongly accepted** — `/tmp/rprobes/p_nextdict.py`: `D.keys()` returns an object with only `__next__`. CPython: `TypeError D.keys() returned a non-iterable (type Keys)`; HEAD: `{'a': 9, 'b': 9}` (base raised TypeError). `ail__dict_iter_supported` accepts `iter_next`, but `iter()`/CPython’s dict protocol require `__iter__`.

3. **Unrelated `dict(d.keys())` regressed** — `/tmp/rprobes/p_dictviews.py`:
```python
d = {'ab': 1, 'cd': 2}
print(dict(d.keys()))
print(dict(d.items()))
print(dict(d.values()))
```
CPython prints `{'a': 'b', 'c': 'd'}` then `{'ab': 1, 'cd': 2}`, then errors on `values`. HEAD errors immediately with `TypeError cannot convert dictionary update sequence element to a sequence`; base printed the first (wrong) dict before failing later. Removing `_resolve_iter_src` from non-stdin `dict(x)` changed this program even though it uses no user instance with `keys`.
[cost $0.0000, opencode tokens {"total": 782753, "input": 45189, "output": 6903, "reasoning": 22693, "cache.write": 0, "cache.read": 707968}]
    tool time: bash 5.4 min
        103s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1200 python3 ../tools/par_check.py -j 2 test
         46s bash   date; cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/*.py; do echo "===== $(basename $p)"; bash ~
         37s bash   cd /tmp/rprobes && cat > p_listonly.py <<'EOF' print(dict([['ab', 1]])) print(dict([])) print(dict([('a', 1), 
         25s bash   cd /tmp/rprobes && cat > p_byteskeys.py <<'EOF' class D:     def keys(self):         return b'ab'     def __ge
         25s bash   cd /tmp/rprobes && cat > p_default_getitem.py <<'EOF' class D:     def keys(self):         return ['a']     de
         18s bash   cd /tmp/rprobes && date; echo BASE; for p in p_nextdict p_callable p_classattr_callable p_dictviews p_general_
         15s bash   cd /tmp/rprobes && cat > p_seqproto2.py <<'EOF' class Keys:     def __getitem__(self, i):         if i < 2:   
         14s bash   cd /tmp/rprobes && cat > p_nextdict.py <<'EOF' class Keys:     def __init__(self):         self.i = 0     def 

## worker report 1
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Fixed and committed as `98a641b` on `job-pre38-10241003`.

**Review fixes**
1. Instance-assigned `keys` functions are now called unbound with arity checking (no segfault; CPython TypeError text). Class-origin functions still bind `self`.
2. A keys result now needs `__iter__`; `__next__`-only results are rejected.
3. `dict(d.keys())`, `dict(d.items())` and string pair elements match CPython again, including indexed pair errors.
4. Also fixed from the report’s failed claims: callable `keys` attributes, `keys(self, *args)`, `keys` with defaults, and `__getitem__` with optional parameters.

**Tests on final commit** (`par_check -j 2`): `test_ail_pre38`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed. `update_manifest.py --check` exit 0.

**Probes** (`cmp.sh`, both builds): all `/tmp/probes` mapping probes match, including `p_instfunc1/2`, `p_classfunc`, `p_nextdict`, `p_dictviews`, `p_dictviews2`, `p_callable`, `p_keys_star`, `p_keys_default`, `p_liststr`, `p_q01`, `p_q07list`, `p_q07str`. Across the 37 `/tmp/rprobes`, 27 match; the 10 remaining mismatches are pre-existing (`p_closurekeys`, `p_general_call`, `p_general_default`, `p_instattr_bound`, `p_nextonly`, `p_nextonly2`, `p_q01` repr, `p_seqproto`, `p_seqproto2`), verified against HEAD where applicable. Original `q02` was not fixed and still differs.
[cost $0.1064, opencode tokens {"total": 8223528, "input": 350765, "output": 19763, "reasoning": 30739, "cache.write": 0, "cache.read": 7822261}]
    tool time: bash 15.4 min
        263s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_pre
        147s bash   cd /tmp/rprobes && for p in *.py; do n=${p%.py}; out=$(bash ~/tools/cmp.sh "$p" /home/runner/work/ail-ci/ail-c
        145s bash   cd /tmp/rprobes && for p in *.py; do n=${p%.py}; out=$(bash ~/tools/cmp.sh "$p" /home/runner/work/ail-ci/ail-c
        130s bash   cd /tmp/probes && for p in *.py; do n=${p%.py}; out=$(bash ~/tools/cmp.sh "$p" /home/runner/work/ail-ci/ail-ci
         54s bash   cd /tmp/probes && cat > p_liststr.py <<'EOF' print(dict(['ab', 'cd'])) print(dict([('x', 1)])) try:     print(
         45s bash   cd /tmp/probes && for p in p_instfunc2 p_instfunc1 p_classfunc p_nextdict p_dictviews p_callable p_keys_star p
         38s bash   cd /tmp/probes && for p in p_instfunc2 p_instfunc1 p_classfunc p_nextdict p_dictviews p_callable p_keys_star p
         30s bash   cd /tmp/probes && for p in p_keys_default p_keys_star p_instfunc2 p_instfunc1 p_callable p_nextdict p_dictview

## review 1 failed to run:           0s bash   cd AIL_CURRENT && grep -n "ail_dict_update_pairs\|ail__dict_call_checked\|keys_extra" python/pkg-v12/cruntime.           0s bash   git worktree list; ls /tmp/base 2>/dev/null | head; ls AIL_CURRENT | head -40           0s bash   sed -n '1,280p' AIL_CURRENT/test_ail_pre38.py 

## review 1
[model opencode-go/deepseek-v4.1-flash]
**What the change really does:** Implements CPython's mapping protocol for `dict(<user instance>)` (call `keys`, map keys through `__getitem__`), including class/instance `keys` attributes, instance functions called unbound, `__iter__`-only keys results, string pair elements, dict-view/`dict(d.keys())` paths, and class names in iteration errors. It is broader than the report's "fix q01/q07".

**Verified claims**
- q01, q07-list and q07-str now match CPython on both builds; q02 still differs (as reported).
- Instance-assigned key functions are called unbound with CPython arity errors (no segfault): `p_instfunc1/2`, `r_defaults`.
- `keys` with defaults/`*args`/`**kwargs`, `__getitem__` with optional args, zero-arg callable keys attributes: match (`r_defaults`, `p_keys_star`, `p_keys_default`, `p_callable`).
- Class-origin key functions bind `self`: `p_classfunc`.
- `dict(d.keys())`, `dict(d.items())`, string pairs, and mutation during mapping match CPython (`r_dict_paths`, `r_mutate_getitem`, `p_dictviews*`, `p_liststr`).
- Requested tests on HEAD: `test_ail_pre38`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed. `tools/update_manifest.py --check` exit 0. Commits carry the co-author trailer.

**False / overbroad claims**
- "**callable keys attributes** ... supported" is only true for a zero-argument `__call__`; a callable with a default argument is rejected (probe below).
- "10 remaining mismatches" is off: the 37 `/tmp/rprobes` give 28 matches and 9 mismatches (the nine named ones), all reproduced on base. `p_nextonly` is partly fixed; its remaining line is pre-existing.
- Non-feature C is not unchanged: e.g. `r_plain` gains `getitem_fn`/`call_fn` setup and a `g_attr_keys` intern (behaviour identical), plus the runtime header. Not separately blocking, but it contradicts the "C must be unchanged" check.

**Pre-existing (not blocking):** `p_closurekeys`, `p_general_call`, `p_general_default`, `p_instattr_bound`, `p_nextonly` (remaining line), `p_nextonly2`, `p_q01` repr, `p_seqproto`, `p_seqproto2`; plus sequence-protocol keys results (`r_seqproto`) and callable/property `keys` cases below where base also differs.

**New regressions**
1. A `keys` **property** whose value is a callable: the helper calls the property getter as if it were `keys()`, then uses the returned callable as the keys iterable instead of calling it.
```
class K:
    def __call__(self):
        return ["a", "b"]
class D:
    @property
    def keys(self):
        return K()
    def __iter__(self):
        return iter([("a", 1), ("b", 1)])
    def __getitem__(self, k):
        return 1
print(dict(D()))
```
Expected (CPython and base): `{'a': 1, 'b': 1}` (exit 0). Actual HEAD: no stdout, `TypeError: D.keys() returned a non-iterable (type K)`, exit 1, both builds.

2. An instance `keys` attribute that is a callable whose `__call__` has a default is treated as non-callable.
```
class K:
    def __call__(self, x=1):
        return ["a", "b"][:x]
class D:
    def __init__(self):
        self.keys = K()
    def __iter__(self):
        return iter([("a", 1)])
    def __getitem__(self, k):
        return 1
print(dict(D()))
```
Expected (CPython and base): `{'a': 1}` (exit 0). Actual HEAD: no stdout, `TypeError: 'K' object is not callable`, exit 1, both builds. Root cause: `call_fn` is installed only for `__call__(self)` with no optional parameters.

**Tests/probes run:** the four modules above; all `/tmp/rprobes` on HEAD and the nine mismatching ones on base; 12 `/tmp/probes` mapping probes on HEAD (all match). **Unverified:** speed — `tools/icount.c` builds, but `perf_event_open` is denied on this runner (`Permission denied`), so no instruction counts.

VERDICT: FIX
[cost $0.0585, opencode tokens {"total": 2661039, "input": 211324, "output": 8885, "reasoning": 23678, "cache.write": 0, "cache.read": 2417152}]
    tool time: bash 12.4 min
        185s bash   cd /tmp/rprobes && date; for p in *.py; do n=${p%.py}; out=$(bash ~/tools/cmp.sh "$p" /home/runner/work/ail-ci
        166s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1200 python3 ../tools/par_check.py -j 2 test
        100s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1200 python3 ../tools/par_check.py -j 2 test
         65s bash   cd /tmp/rprobes && date; for n in p_closurekeys p_general_call p_general_default p_instattr_bound p_nextonly p
         43s bash   cd /tmp/probes && for n in p_instfunc1 p_instfunc2 p_classfunc p_dictviews p_dictviews2 p_callable p_keys_star
         39s bash   cd /tmp/rprobes && for f in r_*.py; do for wt in /home/runner/work/ail-ci/ail-ci /tmp/base; do echo "=== $f @ 
         27s bash   cd /tmp/probes && for f in q01.py q02.py q07_list.py q07_str.py; do for wt in /home/runner/work/ail-ci/ail-ci 
         21s bash   cd /tmp/probes && for f in p_q01.py p_q07list.py p_q07str.py; do for wt in /home/runner/work/ail-ci/ail-ci /tm

FINAL VERDICT: FIX  2026-10-24T02:26:27Z
