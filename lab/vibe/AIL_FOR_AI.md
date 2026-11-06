AIL reads Python 3 syntax and compiles one .py file to a native binary.
Write normal Python 3.12: functions, classes, lists, dicts, sets, tuples, strings,
bytes, loops, comprehensions, exceptions, generators and `with` all work. Type
annotations are optional. The binary is run as `prog [args...]`, so read `sys.argv`,
stdin and write stdout the usual way.

Good to use:
- import sys, math, collections, heapq, functools, bisect, itertools, re, io, struct, json, csv
- sys.argv[i] (str), len(sys.argv), int(x)
- sys.stdin.read(), sys.stdin.readline(), sys.stdin.buffer.read()
- print(...), sys.stdout.write(...), sys.stdout.buffer.write(bytes)
- sys.exit(n) with an int status
- int is a signed 64-bit integer

Refused at compile time, with a named message and exit status 2 or 3:
- an integer literal or constant expression outside int64 (for example 1 << 200)
- a decorator other than @staticmethod, @property, @lru_cache or @cache
- multiple inheritance
Most other constructs compile: when the typed path cannot take one, the default build
falls back to a slower general path with the same output.

A value that leaves int64 at run time stops the program with
`OverflowError: integer overflow in + (ints are 64-bit; --exact-int gives exact ints)`,
exit status 1; it never wraps or silently widens.

Dict views work: `x = d.items()` is fine (the default build handles it, usually on the
general path); calling `d.items()` where it is used is the fast typed form.

When a build is refused, read the message: it names the file, line and construct,
and usually the rewrite. Fix that construct and reply with the whole file again.

The default build may print `note: ... built on the general path` and still work
(about 20x slower, same output). That is not an error.
