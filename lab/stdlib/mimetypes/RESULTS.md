# `mimetypes` coverage results

Build command for every program (default build, `-o` must not exist yet):

```
python3 AIL_CURRENT/ail_chatgpt.py compile lab/stdlib/mimetypes/<program>.py -o /tmp/<program>.out
```

The oracle is `python3 <program>.py` (CPython 3.12.3).  Every program calls `mimetypes.init([])`
first.  `init([])` still reads `mimetypes.knownfiles` on its first call, exactly as CPython does,
so both sides see the same `/etc/mime.types` when the machine has one and both fall back to the
built-in tables when it does not.

## Before

Every program was refused at the import of the module.  The compiler has no library model for
`mimetypes`, so the first refusal after `not in the subset:` is the same for all ten:

```
mimetypes.init (not yet published in NAMES_library.json)
```

| program | default build | first refusal line |
| --- | --- | --- |
| `01_plain_names.py` | refused | `lab/stdlib/mimetypes/01_plain_names.py:3:1: not in the subset: mimetypes.init (not yet published in NAMES_library.json)` |
| `02_paths.py` | refused | `lab/stdlib/mimetypes/02_paths.py:3:1: not in the subset: mimetypes.init (not yet published in NAMES_library.json)` |
| `03_upper_suffix.py` | refused | `lab/stdlib/mimetypes/03_upper_suffix.py:3:1: not in the subset: mimetypes.init (not yet published in NAMES_library.json)` |
| `04_encoding.py` | refused | `lab/stdlib/mimetypes/04_encoding.py:3:1: not in the subset: mimetypes.init (not yet published in NAMES_library.json)` |
| `05_svgz.py` | refused | `lab/stdlib/mimetypes/05_svgz.py:3:1: not in the subset: mimetypes.init (not yet published in NAMES_library.json)` |
| `06_unknown.py` | refused | `lab/stdlib/mimetypes/06_unknown.py:2:1: not in the subset: mimetypes.init (not yet published in NAMES_library.json)` |
| `07_http_url.py` | refused | `lab/stdlib/mimetypes/07_http_url.py:3:1: not in the subset: mimetypes.init (not yet published in NAMES_library.json)` |
| `08_strict_false.py` | refused | `lab/stdlib/mimetypes/08_strict_false.py:3:1: not in the subset: mimetypes.init (not yet published in NAMES_library.json)` |
| `09_extensions.py` | refused | `lab/stdlib/mimetypes/09_extensions.py:3:1: not in the subset: mimetypes.init (not yet published in NAMES_library.json)` |
| `10_add_type_instance.py` | refused | `lab/stdlib/mimetypes/10_add_type_instance.py:3:1: not in the subset: mimetypes.init (not yet published in NAMES_library.json)` |

Result before: **0 built, 0 matched**.

## After

`AIL_CURRENT/stdlib/mimetypes.py` is CPython 3.12's `Lib/mimetypes.py` as AIL source.  The four
rewrites it needs (documented in its module docstring) are: a local `_urlsplit` in place of
`urllib.parse.urlparse` (the compiler refuses `urllib`), `os.fspath` dropped (`url` must be a
str), `os.path.splitdrive` dropped (POSIX identity), and the Windows registry part removed.
`posixpath.splitext`, `open(..., encoding='utf-8')`, `readline()`, the walrus loop and the
dictionaries are built as written.

Ten programs build and match CPython in the default build and with `AIL_UNIFIED_FORCE=1`.  The
default build prints a `note:` that it built on the general path because parameter `strict` of
`MimeTypes.add_type()` is seen as a bool in some calls and a number in others; the C from the
forced general build has the same sha256.

| program | default build | forced general | matches CPython stdout + exit |
| --- | --- | --- | --- |
| `01_plain_names.py` | general (typed fallback note) | general | yes |
| `02_paths.py` | general (typed fallback note) | general | yes |
| `03_upper_suffix.py` | general (typed fallback note) | general | yes |
| `04_encoding.py` | general (typed fallback note) | general | yes |
| `05_svgz.py` | general (typed fallback note) | general | yes |
| `06_unknown.py` | general (typed fallback note) | general | yes |
| `07_http_url.py` | general (typed fallback note) | general | yes |
| `08_strict_false.py` | general (typed fallback note) | general | yes |
| `09_extensions.py` | general (typed fallback note) | general | yes |
| `10_add_type_instance.py` | general (typed fallback note) | general | yes |

Result after: **10 built, 10 match CPython in both builds**.

## Notes

* `07_http_url.py` covers `http://`, `https://`, `ftp://`, a URL whose path is a directory
  (`?file=a.txt`) and two `data:` URLs.  The local `_urlsplit` mirrors `urlparse` for these.
* `scripts that ask for an extension the machine file defines` (for example `.xyz`, `.mid`,
  `.gz` as a type) get the machine's answer on both sides because `init([])` reads
  `knownfiles` in both implementations.  On a machine without `/etc/mime.types` both sides
  use the built-in tables.
* `AIL_CURRENT/test_ail_std_mimetypes.py` builds all ten programs in both modes and compares
  stdout and the exit status with `python3`; it is registered in
  `AIL_CURRENT/tests.d/test_ail_std_mimetypes.txt`.

## Review fixes

Two differences from `urlparse` in `_urlsplit` were reported and fixed.  Probes in `/tmp/probes`
(`pA_urls.py`, `pE_ipv6.py`, `pF_data.py`, `pG_bracket_raise.py`) match CPython in the default
build and with `AIL_UNIFIED_FORCE=1`:

* `urlsplit`'s pre-processing is mirrored: `url.lstrip(_WHATWG_C0_CONTROL_OR_SPACE)` and then
  removal of every `\t`, `\r` and `\n`.  `guess_type(" http://h/a.txt?x=1")` and
  `guess_type("http://h/a.txt\t")` now return `('text/plain', None)`, not `(None, None)`.
* A `[`/`]`-unbalanced netloc raises `ValueError("Invalid IPv6 URL")`, as `urlsplit` does:
  `guess_type("http://[::1/x.txt")` raises and exits 1.  The structural checks of
  `_check_bracketed_netloc` are mirrored too (`x[::1]`, `[a]b`, `[foo]`, `[1.2.3.4]`,
  `[v]`, `[vz.x]`).

Known limitation (not a new program failure): `ipaddress.IPv6Address` is not built, so a
bracketed hostname is accepted when it contains a `:`; CPython would still reject a malformed
IPv6 spelling such as `[:::]` or `[gggg::1]`.  No program in this directory uses one.  A
compiler change to support `ipaddress.IPv6Address` would let `_check_bracketed_netloc` validate
the address exactly.

## Follow-ups (out of scope: compiler files)

None: all ten programs pass without a compiler change.  The typed path could take
`MimeTypes.add_type()` if the `strict` bool/number inference were resolved, but the general
path matches CPython and the fallback only prints a note.
