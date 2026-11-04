# mdlite results

- Date: 2026-11-04
- App commit: `9b93694` (`examples/mdlite/mdlite.py`, 336 lines)
- Oracle: CPython 3.12.3
- Host: GitHub Actions runner, Linux, 4 cores

## Build path

Default build:

```
python3 -B AIL_CURRENT/ail_chatgpt.py compile examples/mdlite/mdlite.py -o /tmp/mdlite
```

It builds on the **general path**. The exact message is:

```
note: examples/mdlite/mdlite.py:158:5: built on the general path (about 20x slower) because Markdown.__init__ must take plain positional arguments, no defaults, *args or **kwargs; run with --strict to see why
```

The first cause is `def __init__(self, text, depth=0)`: a default argument on a
constructor. The app is written the way a Python user writes it, so no
annotations or positional-only fixes were added to force the typed path.

`AIL_UNIFIED_FORCE=1` produced a byte-identical binary
(`sha256 8899c2b73a25b5fd7c3caa777b6d2eda287c1a975922bcd5d210ea991f5f0ed2`,
264,792 bytes), so both modes use the same general path.

## Comparison with CPython

Each case was run as `python3 -B examples/mdlite/mdlite.py FILE` and as
`/tmp/mdlite FILE` (default build) and `/tmp/mdlite_force FILE`
(`AIL_UNIFIED_FORCE=1`). Standard output, standard error and the exit status
were compared byte for byte with `cmp`.

| Input | stdout bytes | exit | CPython == default | CPython == forced |
| --- | --- | --- | --- | --- |
| `data/headings.md` | 420 | 0 | yes | yes |
| `data/inline.md` | 802 | 0 | yes | yes |
| `data/lists.md` | 552 | 0 | yes | yes |
| `data/quotes.md` | 266 | 0 | yes | yes |
| `data/fences.md` | 521 | 0 | yes | yes |
| `data/empty.md` | 0 | 0 | yes | yes |
| `docs/tutorial.md` | 14,084 | 0 | yes | yes |
| `docs/QUICKSTART.md` | 5,352 | 0 | yes | yes |
| `docs/INSTALL.md` | 10,227 | 0 | yes | yes |
| `README.md` | 3,265 | 0 | yes | yes |
| missing file `/tmp/definitely-missing.md` | 0 | 1 | yes (stderr too) | yes (stderr too) |

Standard input (no file argument) was also compared with `data/quotes.md` and
matched. The 20 MB generated corpus below matched byte for byte as well
(27,640,196 bytes of HTML).

Missing-file stderr from both builds:

```
mdlite: cannot open /tmp/definitely-missing.md
```

## 20 MB measurement

Corpus: `python3 examples/mdlite/make_big.py /tmp/mdlite-big/big.md 20`
(seed 20260101, 20,429,882 bytes of Markdown, 27,640,196 bytes of HTML).
All runs: `ulimit -v 1500000`, output to `/dev/null`.

| Metric | CPython 3.12.3 | AIL (default, general path) | Ratio |
| --- | --- | --- | --- |
| Wall time, median of 3 | 3.26 s | 8.82 s | 2.70x slower |
| Wall time, three runs | 3.24 / 3.26 / 3.29 s | 8.79 / 8.82 / 8.83 s | |
| Peak RSS (`/usr/bin/time -v`) | 208,920 kB | 457,744 kB | 2.19x |
| Binary size | n/a (interpreter) | 264,792 bytes | |
| Instructions (`tools/icount.c`) | not measurable — see refusal | not measurable — see refusal | |

Wall-time commands:

```
/usr/bin/time -f "%e %M" python3 -B examples/mdlite/mdlite.py /tmp/mdlite-big/big.md > /dev/null
/usr/bin/time -f "%e %M" /tmp/mdlite /tmp/mdlite-big/big.md > /dev/null
```

`tools/icount.c` was built with
`cc -O2 -w -include signal.h -include stdlib.h -o /tmp/icount tools/icount.c`;
every invocation stops at the first step with:

```
perf_event_open: Permission denied
```

The container does not allow `perf_event_open`, so instruction counts are not
reported.

## Refusals and follow-ups

1. **General path (not a refusal).** Default and forced builds use the general
   path; the exact fallback line is quoted above. Forcing the typed path would
   need annotations or removing the constructor default, which would stop the
   code from being ordinary Python.

2. **Non-BMP code point at run time.** The AIL v2 runtime stores `str` as
   16-bit units. Any input containing a code point above U+FFFF stops loudly.
   Reproducer:

   ```
   $ python3 -c "open('/tmp/emoji.txt','w',encoding='utf-8').write('x\U0001F642y\n')"
   $ /tmp/mdlite /tmp/emoji.txt
   ```

   ```
   AIL internal error: stdin code point above U+FFFF in the 16-bit v2 runtime
   ```

   Exit status 1, versus CPython's exit 0. The hand input `data/inline.md`
   therefore uses the BMP emoji ✨ (U+2728) and covers Japanese and accented
   text; the non-BMP case is recorded here, not fixed. The app itself handles
   🙂 correctly under CPython.

3. **`icount` unavailable.** `perf_event_open: Permission denied`, as above.

## Spelling changes made to let the default build succeed

1. `render_list` originally kept pending items as `[content, children]`
   two-element lists. AIL's nested-list "row" specialization crashed the
   compiler with
   `TypeError: can only concatenate str (not "tuple") to str` in
   `nested_lists.py:84` (`row_class`). It was rewritten to use a tiny
   `ListItem` class with `content` and `children` attributes — an ordinary
   Python spelling for the same data, and a clear single change.

2. The hand input `data/inline.md` uses ✨ instead of 🙂; see refusal 2. The app
   source does not depend on this.
