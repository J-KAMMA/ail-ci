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
  and compares it with a snapshot of the lines taken when the entry was filled.  It drops the
  entry when the content differs, when the entry in `cache` was replaced after it was filled,
  when the path is no longer a readable regular file, or when the file can no longer be decoded
  as UTF-8.  CPython compares `st_size` and `st_mtime` and drops only when `os.stat` fails or
  either value moved.  A rewrite that leaves the content identical is a hit here (CPython would
  drop the entry on a changed mtime); a rewrite to different content of the same size is a miss
  here (CPython would keep the entry when the mtime has not moved).  The comparison uses that
  private snapshot, not the list in the cache, so a caller that mutates the list returned by
  `getlines` keeps its mutation across `checkcache`, as in CPython.  A file that still exists
  but can no longer be opened keeps its entry, matching `os.stat` succeeding in CPython.  An
  entry with `mtime is None` (installed by a caller, as a loader would) is left alone, and a
  one-element lazy entry is skipped, both as in CPython.
* The entry tuple keeps CPython's shape `(size, mtime, lines, fullname)`.  `size` is the number
  of characters read, not counting the `"\n"` this module adds to a last line that lacked one
  (CPython records the file's `st_size`, which is in bytes), and `mtime` is `0` for entries this
  module fills because there is no mtime to record.  Tuples do hold `None`, so an entry seeded
  directly in `cache` keeps whatever `mtime` it was given.  A `MemoryError` from a huge file is
  not caught in `getlines`.
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

# Each `cache` entry as it was when this module filled it, paired with a copy of its lines.
# `checkcache` uses the pair so that a mutation of the list the caller received does not make
# the entry look out of date, while a replacement of the entry itself is noticed.
_snapshots = {}


def clearcache():
    """Clear the cache entirely."""
    cache.clear()
    _snapshots.clear()


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
    """Read `fullname` as UTF-8.

    Returns `(status, lines, size)`.  Status 1 means `lines` are the normalised lines and
    `size` is the number of characters read before a final newline was added; status 0 means
    the file cannot be opened; status 2 means the file exists but is not valid UTF-8.
    """
    if not os.path.isfile(fullname):
        return 0, None, 0
    try:
        with open(fullname, encoding="utf-8") as fp:
            lines = fp.readlines()
    except (UnicodeDecodeError, ValueError):
        # The typed runtime raises UnicodeDecodeError and the general path raises its parent
        # ValueError with the same text; the only ValueError `open` raises here is a decode
        # failure, the mode and encoding being fixed.
        return 2, None, 0
    except OSError:
        return 0, None, 0
    size = 0
    for line in lines:
        size += len(line)
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    return 1, lines, size


def _drop(filename: str):
    """Remove `filename` from both the cache and the snapshots."""
    if filename in cache:
        del cache[filename]
    if filename in _snapshots:
        del _snapshots[filename]


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
            # A lazy entry, leave it lazy.
            continue
        size, mtime, lines, fullname = entry
        if mtime is None:
            # No stat was recorded (an entry seeded by a loader), leave it alone.
            continue
        status, fresh, fresh_size = _read_lines(fullname)
        if status == 2:
            # The file exists but is no longer valid UTF-8: its content cannot be used.
            _drop(filename)
            continue
        if status == 0:
            # The content cannot be read now.  CPython's os.stat still succeeds for a file
            # that exists but cannot be opened (no read permission), so keep the entry; drop
            # it only when the path is gone or is no longer a regular file.
            if not os.path.isfile(fullname):
                _drop(filename)
            continue
        if filename not in _snapshots:
            _drop(filename)
            continue
        snapshot_entry, snapshot_lines = _snapshots[filename]
        if snapshot_entry != entry or fresh != snapshot_lines:
            _drop(filename)


def updatecache(filename: str, module_globals=None):
    """Update a cache entry and return its list of lines.

    If something's wrong, discard the cache entry and return an empty list.
    """
    if filename in cache:
        if len(cache[filename]) != 1:
            _drop(filename)
    if not filename or (filename.startswith("<") and filename.endswith(">")):
        return []

    fullname = filename
    status, lines, size = _read_lines(fullname)
    if status != 1:
        return []
    entry = (size, 0, lines, fullname)
    cache[filename] = entry
    _snapshots[filename] = (entry, list(lines))
    return lines
