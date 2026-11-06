AIL reads Python 3 syntax and compiles one .py file to a native binary.
Write normal Python 3.12: functions, classes, lists, dicts, sets, tuples, strings,
bytes, loops, comprehensions and exceptions all work. Type annotations are optional.
The binary is run as `prog [args...]`, so read `sys.argv`, stdin and write stdout
the usual way.

Good to use:
- import sys, math, collections, heapq, functools, bisect, itertools, re, io, struct
- sys.argv[i] (str), len(sys.argv), int(x)
- sys.stdin.read(), sys.stdin.readline(), sys.stdin.buffer.read()
- print(...), sys.stdout.write(...), sys.stdout.buffer.write(bytes)
- sys.exit(n) with an int status
- int is a signed 64-bit integer

What AIL refuses, at compile time, with a named message and exit status 2 or 3:
- an integer literal or constant expression outside int64 (for example 1 << 200)
- a value that leaves int64 at run time stops the program with
  `OverflowError: integer overflow in + (ints are 64-bit; --exact-int gives exact ints)`,
  exit status 1; it never wraps or silently widens
- a dict view kept in a name (`x = d.items()`): call d.items() where it is used,
  or keep `list(d.items())`
- decorators other than @staticmethod and @lru_cache / @cache
- multiple inheritance, and a `with` block around a `yield`
- stdlib modules outside the supported subset; third-party packages do not exist

When a build is refused, read the message: it names the file, line and construct,
and usually the rewrite. Fix that construct and reply with the whole file again.

The default build may print `note: ... built on the general path` and still work
(about 20x slower, same output). That is not an error.
