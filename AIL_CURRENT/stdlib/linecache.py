"""Cache lines from Python source files.

This is CPython 3.12's Lib/linecache.py as AIL source, reduced to what a compiled program can
provide.  `getline`, `getlines`, `clearcache`, `checkcache`, `updatecache` and the `cache` dict
keep CPython's names, signatures, entry shape and return values: a line number outside
`1..len(lines)` gives `""`, an unreadable or missing file gives `[]` from `getlines` and `""`
from `getline`, and the last line of a file without a final newline is returned with one
appended.

Behaviour differences from CPython, each forced by what the compiler builds:

* The file is opened with `encoding="utf-8"`.  CPython's `tokenize.open` also honours a PEP 263
  coding cookie and a UTF-8 BOM; here a file that is not UTF-8 is read as UTF-8 and a decode
  error gives the empty result, where CPython decodes it.
* `os.stat` is not built, so freshness is the file's *content*: `checkcache` re-reads the file
  and drops the entry when its lines differ (or the file is gone), where CPython compares
  `st_size` and `st_mtime`.  A rewrite that leaves the content identical is a hit here (CPython
  would drop the entry on a changed mtime); a rewrite to different content of the same size is
  a miss here (CPython would keep the entry when the mtime has not moved).
* The entry tuple keeps CPython's shape `(size, mtime, lines, fullname)`; `size` is the number
  of characters read and `mtime` is always `0` (there is no mtime to record, and `None` inside
  a tuple is not built).  A `MemoryError` from a huge file is not caught in `getlines`.
* A relative filename that is not found is not looked up through `sys.path` (`sys.path` used as
  a plain value is not in the subset); `updatecache` returns `[]` instead.  A filename that is
  relative to the working directory still works.
* `lazycache` and the `module_globals` loader path are dropped: they need a module loader with
  a `get_source` method, which a compiled program does not have.  `module_globals` is accepted
  and ignored.
"""

import os

__all__ = ["getline", "getlines", "clearcache", "checkcache", "updatecache", "cache"]


cache = {}


def clearcache():
    """Clear the cache entirely."""
    cache.clear()


def getline(filename: str, lineno: int, module_globals=None):
    """Get a line for a Python source file from the cache.

    Update the cache if it doesn't contain an entry for this file already.
    """
    lines = getlines(filename, module_globals)
    if 1 <= lineno and lineno <= len(lines):
        return lines[lineno - 1]
    return ""


def getlines(filename: str, module_globals=None):
    """Get the lines for a Python source file from the cache.

    Update the cache if it doesn't contain an entry for this file already.
    """
    if filename in cache:
        entry = cache[filename]
        if len(entry) != 1:
            return cache[filename][2]
    return updatecache(filename, module_globals)


def _read_lines(fullname: str):
    """The normalised lines of `fullname`, or None when the file cannot be read."""
    if not os.path.isfile(fullname):
        return None
    try:
        with open(fullname, encoding="utf-8") as fp:
            lines = fp.readlines()
    except (OSError, ValueError):
        return None
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    return lines


def checkcache(filename=None):
    """Discard cache entries that are out of date.

    (This is not checked upon each call!)
    """
    if filename is None:
        filenames = list(cache.keys())
    elif filename in cache:
        filenames = [filename]
    else:
        return

    for filename in filenames:
        entry = cache[filename]
        if len(entry) == 1:
            continue
        size, mtime, lines, fullname = entry
        fresh = _read_lines(fullname)
        if fresh is None or fresh != lines:
            cache.pop(filename, None)


def updatecache(filename: str, module_globals=None):
    """Update a cache entry and return its list of lines.

    If something's wrong, discard the cache entry and return an empty list.
    """
    if filename in cache:
        if len(cache[filename]) != 1:
            cache.pop(filename, None)
    if not filename or (filename.startswith("<") and filename.endswith(">")):
        return []

    fullname = filename
    if not os.path.isfile(fullname):
        return []
    lines = _read_lines(fullname)
    if lines is None:
        return []
    size = 0
    for line in lines:
        size += len(line)
    cache[filename] = size, 0, lines, fullname
    return lines
