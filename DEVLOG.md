# DEVLOG

## 2026-10-23 - print sep/end TypeError names the value's class (job-pre4-10240009)

Review fix on top of the entry below. The new sep/end type check used `ail_type_name`, so
every class instance was reported as `not instance` (a user class and `bytes` both differ
from CPython). Both print checkers now use `ail__tname_c`, which already names the class;
`ail__tname_c` also names an exception object's class now, so
`print(..., sep=e)` with a caught `ValueError` says `not ValueError`. `test_ail_pre4.py`
adds the user-class / bytes / bytearray / caught-exception case on stdout and stderr.

Probes (`/tmp/probes/`, both builds): d_inst, d_sources, d_other, d_names2, d_exc3 all
match CPython. Tests: test_ail_pre4, test_ail_safetynet, test_ail_files,
test_ail_corpus_findings3.

## 2026-10-23 - print sep/end evaluation order and None (job-pre4-10240009)

The first recorded difference still reproduced on this tree: on the general path,
`print(..., end=g(), sep=f())` evaluated `sep` before `end` because every boxed print
looked the keywords up by name instead of following their source order. `_b_print`,
`_call_print_list` and `_call_print_star` now evaluate keyword values in source order
after the positional arguments. The `file=sys.stderr` transform stages its arguments and
keywords in the same order before converting/writing.

The same path also mishandled a non-literal None: `sep=none()` / `end=holder.v` became an
empty separator instead of CPython's defaults on stdout, and the stderr `.join` raised
`AttributeError`; a non-str value was silently stringified on stdout. None now selects the
default and any other non-str raises CPython's `sep/end must be None or a string, not <type>`
TypeError on both streams. New `test_ail_pre4.py` covers source-order keywords, None from
arguments/attributes/list items/dict values on both streams, and the TypeError text.

Probes (`/tmp/probes/`) compared with CPython on both builds: p12b, p12, p12_values,
p12_stdout_star, p12_stderr, p12_typed, p13, p13out, p13_values, p13_out_values, p13_star,
p13_empty, p13_types. Tests: test_ail_pre4, test_ail_safetynet, test_ail_files,
test_ail_corpus_findings3, test_ail_fallback_note all pass.

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
