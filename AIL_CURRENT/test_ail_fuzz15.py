"""Differential fuzz round 15: `re` counts and `json` dumps options, against CPython 3.12.

The programs here are ordinary Python.  CPython runs them as the oracle and each compiled program (the
default build and the general path, AIL_UNIFIED_FORCE=1) must print the same bytes with the same exit
status.

Found with small random programs compared against CPython on both builds:

1. `re.split(..., maxsplit=m)` with a negative `m` split anyway.  CPython treats a negative maxsplit
   as zero splits and returns the subject unchanged; the engine only tested `maxsplit > 0`, so a
   negative value meant no limit and the text was split like `maxsplit=0`.  The same happened for
   `re.sub` / `re.subn` with a negative `count`: CPython replaces nothing, the engine replaced every
   match.  The split/sub/subn loops now stop at a negative maxsplit/count (a zero still means no
   limit), for a literal template, a callable replacement, a compiled pattern, bytes and str.

The rest of the fuzz programs in this area (json.dumps indent / sort_keys / separators / ensure_ascii
and non-ASCII / floats and special values; re.findall groups, split maxsplit, named groups, flags,
sub backreferences, fullmatch) agreed with CPython on both builds except the declared limits listed in
the report: non-BMP strings and surrogate escapes, integers beyond 64 bits in json.loads, a non-ASCII
subject under re.IGNORECASE, and the shapes refused by name (findall with several groups, split with
groups, a non-literal replacement template).
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


def _build_and_run(directory, name, text, general):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


NEGATIVE_SPLIT = r'''import re


def parts(ps: list[str]) -> None:
    for p in ps:
        print("P", len(p), p)


def show(n: int) -> None:
    print("n", n)
    parts(re.split(r",", "a,b,c,d", n))
    parts(re.split(r"\s*", "a b", n))
    parts(re.split(r"", "abc", n))
    print("sub", re.sub(r"a", "-", "aaa", n), re.subn(r"a", "-", "aaa", n))
    print("sub2", re.sub(r"x*", "-", "abc", n), re.subn(r"x*", "-", "abc", n))


def main() -> None:
    for n in [-100, -2, -1, 0, 1, 2, 3, 100]:
        show(n)
    xs: list[int] = [-1, 0, 2]
    d: dict[str, int] = {"n": -1, "zero": 0}
    for i in range(len(xs)):
        print("item", i, re.sub(r"a", "-", "aaa", xs[i]))
        parts(re.split(r",", "a,b,c", xs[i]))
    print("dict", re.sub(r"a", "-", "aaa", d["n"]))
    parts(re.split(r",", "a,b,c", d["n"]))
    parts(re.split(r",", "a,b,c", d["zero"]))
    print("kw", re.sub(r"a", "-", "aaa", count=-1))
    parts(re.split(r",", "a,b,c", maxsplit=-1))
    for p in re.split(rb",", b"a,b,c", -1):
        print("B", len(p), p.hex())
    print("bytes", re.sub(rb"a", b"-", b"aaa", -1), re.subn(rb"a", b"-", b"aaa", -1))
    P = re.compile(r",")
    for p in P.split("a,b,c", -1):
        print("C", len(p), p)
    for p in P.split("a,b,c", maxsplit=-2):
        print("C2", len(p), p)
    print("compiled", P.sub("-", "aaa", -1), P.subn("-", "aaa", -1))
    print("callable", re.sub(r"a", lambda m: "-", "aaa", -1),
          re.sub(r"a", lambda m: "-", "aaa", 2))


main()
'''

POSITIVE_COUNTS = r'''import re


def parts(ps: list[str]) -> None:
    for p in ps:
        print("P", len(p), p)


for n in [0, 1, 2, 3, 4, 100]:
    print("n", n)
    parts(re.split(r",", "a,b,c,d", n))
    parts(re.split(r"", "ab", n))
    parts(re.split(r"x*", "ab", n))
    print("sub", re.sub(r"a", "-", "aaaa", n), re.subn(r"a", "-", "aaaa", n),
          re.sub(r"", "-", "ab", n))
'''

JSON_DUMPS = r'''import json

d = {"b": [1.0, -0.0, float("inf")], "a": {"c": 2}, "e": [], "f": {}}
print(json.dumps(d, indent=0, sort_keys=True))
print(json.dumps(d, indent=-3, sort_keys=True, separators=(",", ":")))
print(json.dumps(d, indent="\t", ensure_ascii=False, sort_keys=True))
print(json.dumps(d, indent="", separators=(";", "="), sort_keys=True))
e: dict[int, int] = {10: 1, 2: 2, -1: 3, 100: 4}
print(json.dumps(e))
print(json.dumps(e, sort_keys=True))
print(json.dumps(e, sort_keys=True, indent=1))
s = "a\x00\x7f caf\u00e9\n\t\"\\"
print(json.dumps(s))
print(json.dumps(s, ensure_ascii=False))
print(json.dumps([True, False, None, 1, 1.5, "é"], indent=2))
print(json.dumps({"x": float("nan")}, sort_keys=True, allow_nan=True))
try:
    print(json.dumps({"x": [float("-inf")]}, allow_nan=False))
except ValueError as exc:
    print("ValueError", exc)
'''

JSON_LOADS_EDGES = r'''import json

texts: list[str] = [
    '{}', '[]', '{"a": 1, "a": 2}', '[1, 2, 3]',
    ' {"b": [true, false, null], "a": "caf\\u00e9"} ',
    '1e400', '-0', '0.0', '1.5e-3', '1e-400'
]
for t in texts:
    try:
        v = json.loads(t)
        print(repr(v), json.dumps(v, sort_keys=True))
    except Exception as exc:
        print(type(exc).__name__, exc)
'''


class Fuzz15Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz15-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_negative_split_and_sub_count(self):
        self.check('re_negative_counts', NEGATIVE_SPLIT)

    def test_zero_and_positive_counts_stay_unlimited(self):
        self.check('re_positive_counts', POSITIVE_COUNTS)

    def test_json_dumps_options(self):
        self.check('json_dumps_options', JSON_DUMPS)

    def test_json_loads_edges(self):
        self.check('json_loads_edges', JSON_LOADS_EDGES)


if __name__ == '__main__':
    unittest.main()
