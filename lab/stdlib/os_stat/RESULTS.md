# `os.stat` / `os.lstat` / `os.fspath` / `os.scandir` and the metadata `os.path` functions

Build command for one program (default build, `-o` must not exist yet):

```
python3 -B AIL_CURRENT/ail_chatgpt.py compile lab/stdlib/os_stat/<program>.py -o /tmp/<program>.out
```

The general path is the same command with `AIL_UNIFIED_FORCE=1`. The oracle is
`python3 -B <program>.py` run in `lab/stdlib/os_stat` (CPython 3.12.3): the programs read the fixed
tree in `data/` with relative paths. Programs print sizes, `stat` predicates, booleans and sorted
names only, never a raw timestamp, because two runs of the same file can differ.

`data/` holds `a.txt` (6 bytes), `b.bin` (20), `empty.txt` (0), `sub/inner.txt` (3) and
`link.txt -> a.txt`. `os.symlink` is not built, so the symlink is a committed relative symlink
instead of one the program creates in a temp directory; `lstat` / `stat` / `samefile` are exercised
on it the same way.

## Before

Every program was refused at its first `os` call, in the default build and on the general path:

| program | first refusal |
| --- | --- |
| `01_sizes.py` | not in the subset: os.stat is not built |
| `02_kinds.py` | not in the subset: os.stat is not built |
| `03_mtime_ns.py` | not in the subset: os.stat is not built |
| `04_lstat.py` | not in the subset: os.lstat is not built |
| `05_missing.py` | not in the subset: os.lstat is not built |
| `06_expanduser.py` | not in the subset: os.path.expanduser is not built |
| `07_scandir.py` | not in the subset: os.scandir is not built |
| `08_scandir_context.py` | not in the subset: os.scandir is not built |
| `09_samefile.py` | not in the subset: os.stat is not built |
| `10_fspath.py` | not in the subset: os.fspath is not built |
| `11_expandvars.py` | not in the subset: os.path.expandvars is not built |
| `12_normcase_times.py` | not in the subset: os.stat is not built |

Result before: **0 built, 12 refused**.

## After

`AIL_CURRENT/test_ail_os_stat.py` builds and runs every program in the default build and with
`AIL_UNIFIED_FORCE=1`, and compares stdout, stderr and the exit status with CPython:

```
python3 -B AIL_CURRENT/test_ail_os_stat.py
```

Result after: **12 of 12 build and match CPython in both builds, all 12 typed** (a default build
that falls back to the general path fails the test).

What is built:

* `os.stat(path)`, `os.lstat(path)` returning a `stat_result` with `st_mode`, `st_ino`, `st_dev`,
  `st_nlink`, `st_uid`, `st_gid`, `st_size`, `st_atime` / `st_mtime` / `st_ctime` (float) and
  `st_atime_ns` / `st_mtime_ns` / `st_ctime_ns` (int). A missing path raises
  `FileNotFoundError: [Errno 2] No such file or directory: 'x'` worded by the shared C runtime.
* `os.scandir(path)` in `for entry in os.scandir(p):` and in `with os.scandir(p) as it:`, with
  `DirEntry.name`, `.path`, `.is_dir()`, `.is_file()`, `.is_symlink()`, `.stat()`, `.lstat()` and
  `.inode()`; entries come in the order the OS returns them.
* `os.fspath(p)` for str and bytes (identity); any other literal is refused by name on the typed
  path (`os.fspath(3) raises TypeError: expected str, bytes or os.PathLike object, not int`) and
  raised as that `TypeError` on the general path. `os.path.normcase` (identity on POSIX, lower case
  and `\` on the nt target), `expanduser` (`~` and `~/...` from `HOME`, even when `HOME` is empty;
  the passwd entry when `HOME` is unset), `expandvars` (`$NAME`,
  `${NAME}`, an unset name left as written), `getmtime` / `getatime` / `getctime`, `samefile`,
  `samestat`.

## The stdlib census bucket "os.X is not built"

Before: 23 modules whose only reason was an `os` name this task builds. Base: integ `0bb1bf7b`,
`lab/stdcensus/RESULTS.md`. After: the same 14 modules that name one of the functions above were
rebuilt with this compiler (`lab/stdcensus/run.py`'s `census_one`, module source copied beside
`main.py`); every one of them gets past its old reason.

| module | before (first reason) | after (first reason) |
| --- | --- | --- |
| `bdb` | bdb.py:52:13: not in the subset: os.path.normcase is not built. Built: join exists isfile isdir islink lexists getsize basename dirname split splitext abspat... | bdb.py:560:9: one `import` statement mixes local modules and others; the compiler needs them apart. |
| `configparser` | configparser.py:688:17: not in the subset: os.fspath is not built. Built: os.getcwd chdir listdir mkdir makedirs remove unlink rmdir rename replace getenv en... | configparser.py:679:9: not in the subset: io used here is not built. Built: os.getcwd chdir listdir mkdir makedirs remove unlink rmdir rename replace getenv environ walk, os.sep linesep name curdir, and the os.path funct |
| `filecmp` | filecmp.py:53:5: not in the subset: os.stat is not built. Built: os.getcwd chdir listdir mkdir makedirs remove unlink rmdir rename replace getenv environ wal... | filecmp.py:145:9: not in the subset: os used here is not built. Built: os.getcwd chdir listdir mkdir makedirs remove unlink rmdir rename replace getenv environ walk, os.sep linesep name curdir, and the os.path functions  |
| `fnmatch` | fnmatch.py:34:5: not in the subset: os.path.normcase is not built. Built: join exists isfile isdir islink lexists getsize basename dirname split splitext abs... | fnmatch.py:53:5: not in the subset: posixpath used here is not built. Built: os.getcwd chdir listdir mkdir makedirs remove unlink rmdir rename replace getenv environ walk, os.sep linesep name curdir, and the os.path func |
| `genericpath` | genericpath.py:19:9: not in the subset: os.stat is not built. Built: os.getcwd chdir listdir mkdir makedirs remove unlink rmdir rename replace getenv environ... | genericpath.py:121:5: not in the subset: os.fstat is not built. Built: os.getcwd chdir listdir mkdir makedirs remove unlink rmdir rename replace getenv environ walk, os.sep linesep name curdir, and os.path join exists is |
| `linecache` | linecache.py:72:13: not in the subset: os.stat is not built. Built: os.getcwd chdir listdir mkdir makedirs remove unlink rmdir rename replace getenv environ ... | not in the subset: functools.partial() of anything but a def or lambda of the program with plain parameters (its number of parameters must be known; no callable instances on the general path) |
| `netrc` | netrc.py:70:13: not in the subset: os.path.expanduser is not built. Built: join exists isfile isdir islink lexists getsize basename dirname split splitext ab... | netrc.py:5:1: one `import` statement mixes local modules and others; the compiler needs them apart. |
| `posixpath` | posixpath.py:54:5: not in the subset: os.fspath is not built. Built: os.getcwd chdir listdir mkdir makedirs remove unlink rmdir rename replace getenv environ... | posixpath.py:278:17: not in the subset: os.getuid is not built. Built: os.getcwd chdir listdir mkdir makedirs remove unlink rmdir rename replace getenv environ walk, os.sep linesep name curdir, and os.path join exists is |
| `pstats` | pstats.py:145:17: not in the subset: os.stat is not built. Built: os.getcwd chdir listdir mkdir makedirs remove unlink rmdir rename replace getenv environ wa... | pstats.py:50:9: not in the subset: name 'str' is not defined |
| `tabnanny` | tabnanny.py:88:13: not in the subset: os.path.normcase is not built. Built: join exists isfile isdir islink lexists getsize basename dirname split splitext a... | not in the subset: a class body statement other than def/assignment/pass/docstring in tabnanny.Whitespace |
| `tempfile` | tempfile.py:217:9: not in the subset: os.lstat is not built. Built: os.getcwd chdir listdir mkdir makedirs remove unlink rmdir rename replace getenv environ ... | tempfile.py:262:13: not in the subset: os.fsencode is not built. Built: os.getcwd chdir listdir mkdir makedirs remove unlink rmdir rename replace getenv environ walk, os.sep linesep name curdir, and os.path join exists i |
| `trace` | trace.py:134:5: not in the subset: os.path.normcase is not built. Built: join exists isfile isdir islink lexists getsize basename dirname split splitext absp... | trace.py:147:5: not in the subset: os.path.splitdrive is not built. Built: join exists isfile isdir islink lexists getsize basename dirname split splitext abspath normpath isabs relpath |
| `tracemalloc` | tracemalloc.py:339:5: not in the subset: os.path.normcase is not built. Built: join exists isfile isdir islink lexists getsize basename dirname split splitex... | tracemalloc.py:5:1: name 'os' is bound by an import in tracemalloc.py and by another import in linecache.py; this compiler keeps standard-library names unrenamed, so the two would collide. |
| `uu` | uu.py:59:21: not in the subset: os.stat is not built. Built: os.getcwd chdir listdir mkdir makedirs remove unlink rmdir rename replace getenv environ walk, o... | uu.py:137:13: not in the subset: os.altsep is None on this target; there is no None str here |

All 14 changed their first reason: **14 of the 23** get past their `os` reason (target: 10). Most now
stop on the next `os` name, which is outside this task. Re-run after the review fixes
(`run.py -j 2 --only ... -o /tmp/...`): all 14 first reasons above reproduce exactly.

* `filecmp` -> `os.path.normcase` passed as a value (`map(os.path.normcase, ...)`), not a call.
* `genericpath`, `tempfile` -> `os.fstat` / `os.fsencode` (the file layer has no OS file descriptors).
* `posixpath`, `trace` -> `os.getuid` / `os.path.splitdrive`.
* `uu` -> `os.altsep is None` (there is no `None` str in the subset).
* `bdb`, `netrc`, `tracemalloc` -> an `import` the compiler cannot split (`import` mixed with local
  modules / the same name bound by two imports).
* others -> unrelated reasons (`str` not defined in a class body, `functools.partial`, ...).

The other 9 modules of the bucket (`_osx_support`, `cgitb`, `getpass`, `imghdr`, `mailcap`, `pipes`,
`pty`, `socket`, `socketserver`, `subprocess`) name `os.system`, `os.fdopen`, `os.open`, `os.PathLike`,
`os.popen`, `os.openpty`, `os._get_exports_list`, `os.waitpid` and `os.confstr`; they are unchanged.

## General-path gaps and limits

* **bytes paths.** `os.stat(b"...")` is refused by name on the typed path
  (`os.stat() with a bytes path is not built; write instead: pass the path as str`); the general path
  builds it and raises `TypeError` at run time. A bytes path held in a variable reaches the same
  `TypeError` on both paths. This is the state `os.path.getsize` was already in.
* **`os.fstat`** needs an OS file descriptor, which the file layer's handles are not; not built.
* `stat_result` is an attribute object only: no tuple indexing, no `st_blksize` / `st_blocks` /
  `st_rdev`. `st_*time` is `st_*time_ns / 1000000000` (one float division of the ns field).
* `os.scandir` is built in `for ... in os.scandir(...)` and `with os.scandir(...) as it:`; `list()`,
  `next()` and passing the iterator around are not built.
* `expanduser("~user")` is not expanded (only `~` and `~/...`); `~` follows CPython for a set,
  empty and unset `HOME`.
* `os.path.normcase` is the identity on POSIX; the nt target lowers case and turns `/` into `\`.

## Runtime files touched

Only one runtime source changed: `AIL_CURRENT/python/pkg-v12/ailfile_core.h`, the C file whose
`ailf_scandir` already answered `os.listdir` / `os.scandir` (it gained `ailf_stat_record`, reached
through the existing `_ail_os_scandir` primitive in mode 2/3). The prelude AIL helpers
(`_AilStatResult`, the DirEntry/scandir classes, `normcase`, `expanduser`, `expandvars`,
`samefile`, `samestat`, `_ail_fspath`) are registered from `filelower.py`, which is one of the
compiler files this task allows; `filelib_prelude.py` is unchanged. `filelower.py` also holds the
lowering.

## Review fixes (second round)

* `with os.scandir(p) as it:` now scopes `it` to the `with` body only; a later ordinary
  `for x in it:` over a list/str is no longer lowered to `it.advance()`, and a nested function
  whose parameter or local is named `it` shadows the marker.
* `os.fspath(3)`: the typed path refuses by name, the default build falls back to the general path
  and raises `TypeError: expected str, bytes or os.PathLike object, not int` (`q_fspath_int.py`).
* `expanduser`: `HOME` empty gives `/` for `~` and `/x` for `~/x`; `HOME` unset falls back to the
  passwd entry (both builds, `q_expanduser.py` with `HOME` unset, empty and with trailing slashes).
* The four `filelib_prelude.py` snippets moved into `filelower.py` (see "Runtime files touched").
