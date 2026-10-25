"""Differential round 36: KeyError text, args and repr on the general path.

Found with small programs compared against CPython on both builds:

A missing dict key (and `dict.pop`/`del d[k]`, `dict.popitem` on an empty dict,
`set.remove`, `set.pop` on an empty set) raised KeyError with the already
quoted text as its only argument on the general path. `str(e)` was right, but
`e.args` was ("'k'",) instead of ('k',), and `repr(e)` showed
KeyError("'k'") instead of KeyError('k').  The runtime now keeps the original
key as the argument and stores CPython's repr(key) as the message, the same
shape the typed path and `raise KeyError(k)` already had.

The programs below keep the shapes compared with CPython on both builds,
including int, bool, None and float keys, empty/special-character strings,
values reaching the lookup through an argument, a list item, an attribute and
a dict value, and nested/re-raised exceptions.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

KEY_TEXT = r'''def main() -> None:
    d = {"a": 1, "it's": 2, 'say "hi"': 3, "": 4, "tab\there": 5, "e\u00e9\u65e5": 6}
    for k in ["zz", "it's", 'say "hi"', "", "tab\there", "e\u00e9\u65e5"]:
        try:
            print(d[k])
        except KeyError as e:
            print("K", str(e), repr(e), e.args)
    n = {1: 1, -2: 2}
    for k in [577, -3, 0, 9223372036854775807, -9223372036854775807 - 1]:
        try:
            print(n[k])
        except KeyError as e:
            print("N", str(e), repr(e), e.args)


main()
'''

KEY_METHODS = r'''def main() -> None:
    d = {"a": 1, "it's": 2, "": 3}
    for k in ["zz", "it's", ""]:
        try:
            print(d.pop(k))
        except KeyError as e:
            print("pop", str(e), repr(e), e.args)
        try:
            del d[k]
        except KeyError as e:
            print("del", str(e), repr(e), e.args)
    e1: dict[str, int] = {}
    try:
        print(e1.popitem())
    except KeyError as e:
        print("popitem", str(e), repr(e), e.args)
    s: set[int] = set()
    try:
        print(s.pop())
    except KeyError as e:
        print("setpop", str(e), repr(e), e.args)
    t = {"a"}
    for k in ["zz", "it's"]:
        try:
            t.remove(k)
        except KeyError as e:
            print("remove", str(e), repr(e), e.args)


main()
'''

KEY_SOURCES = r'''class C:
    def __init__(self, k: str) -> None:
        self.k = k


def get(d, k) -> None:
    try:
        print(d[k])
    except KeyError as e:
        print("get", str(e), repr(e), e.args)


def main() -> None:
    d = {"a": 1}
    c = C("it's")
    keys = ["zz", "a", ""]
    box = {"k": "say \"hi\"", "n": -5}
    get(d, "zz")
    get(d, c.k)
    get(d, keys[0])
    get(d, box["k"])
    get(d, box["n"])
    try:
        print(d[keys[2]])
    except KeyError as e:
        print("empty", str(e), repr(e), e.args)
    n = {1: 1}
    get(n, 0)
    get(n, -9223372036854775807 - 1)
    get(n, 9223372036854775807)


main()
'''

KEY_NESTED = r'''def main() -> None:
    d = {"a": {"b": 1}}
    try:
        print(d["a"]["zz"])
    except KeyError as e:
        print("nested", str(e), repr(e), e.args)
    try:
        print(d["x"]["b"])
    except KeyError as e:
        print("outer", str(e), repr(e), e.args)
    saved = []
    for k in ["q", "r"]:
        try:
            print(d[k])
        except KeyError as err:
            saved.append(str(err))
            saved.append(repr(err))
    print(saved)
    try:
        try:
            raise KeyError("in")
        except KeyError as e:
            print("raised", str(e), repr(e), e.args)
            raise
    except KeyError as e:
        print("again", str(e), repr(e), e.args)
    q = {True: 1, None: 2, 1.5: 3}
    for k in [False, 0, "x", 2.5, None]:
        try:
            print(q[k])
        except KeyError as e:
            print("Q", str(e), repr(e), e.args)


main()
'''


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


class Fuzz36Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz36-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_key_text(self):
        self.check('key_text', KEY_TEXT)

    def test_key_methods(self):
        self.check('key_methods', KEY_METHODS)

    def test_key_sources(self):
        self.check('key_sources', KEY_SOURCES)

    def test_key_nested(self):
        self.check('key_nested', KEY_NESTED)


if __name__ == '__main__':
    unittest.main()
