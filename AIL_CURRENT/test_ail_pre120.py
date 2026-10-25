"""pre120: Counter(mapping) keeps the mapping's values, as CPython's constructor does.

CPython 3.12's Counter.update(mapping) does `dict.update` when the counter is
empty and only adds `count + self.get(elem, 0)` when it is not.  A fresh
constructor is empty, so `Counter({"a": "x"})` holds the string `"x"`; the
general path added 0 + "x" for every mapping entry and raised TypeError.  The
runtime now takes the empty-counter branch for the constructor (and for
`Counter().update(mapping)`), while a non-empty update still adds counts and
keeps CPython's operand order in the TypeError it can raise.  The same change
keeps Counter's repr in most_common order for string counts and names the
operator CPython names when a non-numeric count is compared with 0.

Each program is built on both builds and compared with CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

CTOR_VALUES = r'''from collections import Counter


def show(src):
    try:
        c = Counter(src)
        print(repr(c), dict(c), len(c))
    except Exception as e:
        print(type(e).__name__, str(e))


def main():
    cases = [
        {},
        {"a": "x"},
        {"a": None},
        {"a": [1, 2]},
        {"a": (1, 2)},
        {"a": True},
        {"a": 2},
        {"a": -1},
        {"a": 0},
        {"a": 1.5},
        {1: "x"},
        {(1, 2): "y"},
        {"a": "x", "b": "y"},
        {"a": 2, "b": 1},
        {"a": -2, "b": 3},
        {"a": 9007199254740993},
    ]
    for src in cases:
        show(src)


main()
'''

CTOR_SOURCES = r'''from collections import Counter


class Box:
    def __init__(self, m):
        self.m = m


def make(m):
    return Counter(m)


def through_arg(m):
    return Counter(m)


def main():
    src = {"k": "x"}
    print(Counter(src))
    print(through_arg(src))
    print(make({"z": None}))
    xs = [{"a": "v"}, {"b": 2}]
    print(Counter(xs[0]))
    print(Counter(xs[1]))
    box = Box({"q": "w"})
    print(Counter(box.m))
    table = {"t": {"r": "s"}}
    print(Counter(table["t"]))
    alias = src
    print(Counter(alias))
    inner = Counter({"n": "m"})
    print(Counter(inner))
    print(Counter({}))

    keep = {"a": 7}
    copied = Counter(keep)
    keep["a"] = 9
    keep["b"] = 1
    print(copied, dict(copied), "b" in copied)


main()
'''

UPDATE_SEMANTICS = r'''from collections import Counter


def run(start, upd):
    try:
        c = Counter(start)
        print("start", repr(c))
    except Exception as e:
        print("ctor err", type(e).__name__, e)
        return
    try:
        c.update(upd)
        print("after", repr(c), dict(c), len(c))
    except Exception as e:
        print("update err", type(e).__name__, e, "state", repr(c))


def main():
    run({}, {"a": "x"})
    run({"a": 1}, {"b": "x"})
    run({"a": "x"}, {"a": 2})
    run({"a": 2}, {"a": "x"})
    run({"a": 1}, {})
    run({}, {})
    run({"a": "x"}, {})
    run({"a": 2}, {"a": 3, "b": 4})
    c = Counter()
    c.update({"a": "x"})
    print(repr(c))
    c = Counter()
    c.update([1, 1, 2])
    print(repr(c))
    c = Counter({"a": 1})
    c.update(c)
    print(repr(c))
    c = Counter()
    c.update(c)
    print(repr(c), len(c))


main()
'''

MISC = r'''from collections import Counter


def main():
    c = Counter({"a": "x"})
    print(c["a"], c["missing"], len(c), dict(c))
    print("a" in c, c.get("a"), c.get("missing"))
    print(list(c.items()), list(c.keys()), list(c.values()))
    print(c.most_common())
    print(c.most_common(5), c.most_common(0), c.most_common(-1))
    print(c.copy())
    c2 = Counter({"b": "y"})
    print(c2)
    c["a"] = 5
    print(c)
    for left, right in ((c, c2), (c2, c)):
        try:
            print(left + right)
        except Exception as e:
            print(type(e).__name__, e)
    print(dict(c))


main()
'''

PLAIN_UNAFFECTED = r'''from collections import Counter


def main():
    print(Counter("aab"))
    print(Counter([1, 1, 2]))
    print(Counter())
    d = {}
    d.update({"a": "x"})
    print(d)
    c = Counter({"a": 1})
    c.update(Counter({"b": 2}))
    print(c)
    plain = {"a": 1}
    plain.update({"a": "x"})
    print(plain)


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


class Pre120Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-pre120-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_counter_constructor_values(self):
        self.check('counter_ctor_values', CTOR_VALUES)

    def test_counter_constructor_sources(self):
        self.check('counter_ctor_sources', CTOR_SOURCES)

    def test_counter_update_semantics(self):
        self.check('counter_update_semantics', UPDATE_SEMANTICS)

    def test_counter_string_counts(self):
        self.check('counter_misc', MISC)

    def test_plain_dict_and_iterable_unaffected(self):
        self.check('counter_plain_unaffected', PLAIN_UNAFFECTED)


if __name__ == '__main__':
    unittest.main()
