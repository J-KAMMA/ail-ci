# DEVLOG

## 2026-10-23 - Fix __slots__ review regressions (job-pre6-10240010)

The reviewer of `8c7368a` found three defects in the slot check. Fixes:

* Builtin exception classes are created directly in `ail_ctx_init` (zeroed memory), so their
  `n_slots` stayed 0 and every caught `ValueError` became slot-only. They now get
  `slot_ids = NULL`, `n_slots = -1` (plus empty `class_attr_ids`), so `e.custom = 5` works
  again; `ail__free_payload` also frees the two class arrays.
* `_class_readonly` now collects method names (except internal `__ail_set_*` setter keys)
  as well as class-body attributes, and `_register_class` adds those names to `attr_names`
  for a slots class. `c.f = 3` now says `'C' object attribute 'f' is read-only`.
* The class-body `attr_names` update is gated on `__slots__`, so a class without slots no
  longer emits `g_attr_*` names it never stores (the generated C for `n1` now matches base).

`test_ail_pre6` gained a builtin-exception-attribute case and a method/class-attribute
read-only case, both built on the default and forced-general paths. Probes in
`/tmp/probes/slots_exc_attrs.py`, `slots_method_ro.py` and the existing slots probes all
match CPython on both builds; `n1`'s generated `g_attr_*` set is identical to base.

## 2026-10-23 - Enforce __slots__ on the general path (job-pre6-10240010)

fuzz67 p18 was still a difference on this tree: the general path ignored a class's
`__slots__`, so `c.b = 3` on a class declaring only `a` succeeded and `c.b` read 3,
where CPython raises AttributeError. The typed path already refused the unknown field;
both `bash ~/tools/cmp.sh` builds fell back to the general path and printed `1 3`.

`pyboxed2.py` now records a class's `__slots__` (a literal string or a tuple/list of
strings; anything else is refused by name), including inherited slots, and emits the
allowed names plus the class-body names onto the class object. `cruntime.py`'s v2
runtime checks every attribute store against them: an undeclared name raises CPython's
`'C' object has no attribute 'b'`, while assigning a class-body name raises
`'C' object attribute 'PASS' is read-only`. `setattr()` uses the same checked store.
A class with an inherited `__dict__` (a base without `__slots__`, a builtin exception
base, or `__dict__` in `__slots__`) still accepts arbitrary attributes.

The new `test_ail_pre6.py` builds the case through the default and forced-general
paths and compares stdout/exit with CPython, and checks the dynamic-`__slots__`
refusal. Probes in `/tmp/probes/slots*.py` cover empty/string/tuple slots, inheritance,
class attributes, `setattr`, aliases through an argument, list item, attribute and dict
value, and no-slots classes; all match CPython or are refused by name.

## 2026-10-23 - C compiler step cache (job-ctime3-10232149)

The base export already contains the content-addressed `cc` layer in
`AIL_CURRENT/python/pkg-v12/buildcache.py` (`buildcache.run_cc`, activated by `--cache`, stored under
`$AIL_CACHE` / `~/.cache/ail`, off with `AIL_NO_CACHE=1` or `--no-cache`). The task says not to add
a second cache when one already exists, so this job verifies and measures that layer and adds a
regression test for the exact reuse case:

* `test_changed_source_with_the_same_generated_c_hits_the_cc_cache` changes a typed local's name,
  which changes the merged source text (a new front-end entry) but not the generated C: the C
  compiler step is skipped and the executable is byte-identical.

Measurement on this 4-core runner, gcc 13.3, median of 5 runs, `AIL_CACHE` in a temporary
directory. "before" is `AIL_NO_CACHE=1`; "after" is a cache warm from the same C text with a new
front-end key (a renamed local), so the front end runs but the C compiler step hits. Wall time is
the whole `ail_chatgpt.py compile`; C time is the sum of the compiler wrapper's own runs (after
includes the cache's one-time toolchain probes).

| gdev program | wall before | C before | wall after | C after | outputs |
| --- | ---: | ---: | ---: | ---: | --- |
| g00_000 | 1.245 s | 0.241 s | 1.177 s | 0.013 s | identical |
| g00_002 | 1.427 s | 0.393 s | 1.186 s | 0.012 s | identical |
| g00_004 | 2.540 s | 1.418 s | 1.279 s | 0.012 s | identical |

Output SHA-256 values were equal for every before/after pair. With an unchanged source the whole
front-end cache also hits, so the compiler step is not run at all.
