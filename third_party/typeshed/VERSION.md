# Vendored typeshed stdlib subset

- Upstream: https://github.com/python/typeshed
- Commit: `bd58d637aaa73ec8d7a9ec5e2ad8809a5dd86272` (shallow clone of `main`)
- Commit date: 2026-11-04T09:37:47+01:00
- License: Apache-2.0 (see `LICENSE`, copied unchanged). First line:
  `The "typeshed" project is licensed under the terms of the Apache license, as`
- Total bytes of this directory (excluding this file): 475737 (under the 1.5 MB cap)

Only `stdlib/<module>.pyi` (or `<pkg>/__init__.pyi`) is copied; no third-party stubs, no tests.

## Module list

The list is derived from the modules AIL already builds, not guessed:

- `genlib.TABLE` keys: datetime, functools, graphlib, heapq, itertools, json, math, pprint, random, statistics
- `stdlib3.MODULES`: random, itertools, functools, json
- `stdlib4.py` / `stdlib5.py` / `stdtop.py` module docstrings: csv, datetime, fractions, enum, collections,
  random, keyword, string, calendar, abc, array, io, statistics, decimal, unicodedata, ipaddress, html
- directories of `lab/stdlib/`: array, base64, bisect, collections, csv, datetime, decimal, fractions, graphlib,
  hashlib, heapq, json, math, numbers, pprint, random, re, shlex, sqlite3, statistics, string
- `AIL_CURRENT/stdlib/*.py`: shlex, zlib
- plus: math, sys, os, os.path, time, string, operator

The union, in sorted order:

abc, array, base64, bisect, builtins, calendar, collections, csv, datetime, decimal, enum, fractions, functools,
graphlib, hashlib, heapq, html, io, ipaddress, itertools, json, keyword, math, numbers, operator, os, os.path,
pprint, random, re, shlex, sqlite3, statistics, string, sys, time, unicodedata, zlib

`os` is vendored as `stdlib/os/__init__.pyi` plus `stdlib/os/path.pyi`; `collections`, `json`, `math`,
`sqlite3`, `string`, `html`, `io`(file), `sys`(package) follow their upstream layout. `builtins.pyi` is included.

### Support stubs (re-exported by the modules above)

These are not modules AIL builds by themselves; their stubs are vendored because a listed module re-exports
their names (`from _heapq import *`, `from _csv import reader as reader`, `from _io import StringIO as StringIO`).
The converter copies the re-exported names into the importing module, so `heapq.heappop`, `csv.reader` and
`io.StringIO` have signatures:

_heapq, _bisect, _io, _csv, _hashlib, _random, _decimal, _operator, posixpath, genericpath
