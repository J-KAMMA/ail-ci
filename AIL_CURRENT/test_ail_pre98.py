"""pre98: a Counter reached through a dict value keeps Counter's missing-key behaviour.

CPython's Counter is a dict subclass with `__missing__` returning 0 without
inserting the key.  The general path only knew that for a Counter whose static
kind it could see; a Counter reached through a dict value (or an argument, a
list item, an attribute, a return value, an alias) went through the generic
dict getitem and raised KeyError.  The runtime now applies Counter.__missing__
in the generic getitem and in the augmented-assignment probe, so
`table["k"]["y"] += 1` starts from 0 and stores 1, as CPython does.

The programs keep plain-dict misses as KeyError, check that a read does not
insert, and cover existing and negative counts.  Each program is built on both
builds and compared with CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

COUNTER_DICT_VALUE = r'''from collections import Counter


def main():
    table = {"k": Counter()}
    table["k"]["y"] += 1
    print(table["k"]["y"], dict(table["k"]), len(table["k"]))
    table["k"]["y"] += 2
    table["k"]["z"] = 5
    table["k"]["y"] += 1
    print(table["k"]["y"], dict(table["k"]), len(table["k"]))
    print(table["k"]["missing"], len(table["k"]), "missing" in table["k"])
    other = {"c": Counter()}
    other["c"]["a"] = -2
    other["c"]["a"] += 1
    other["c"]["b"] += 4
    print(other["c"]["a"], other["c"]["b"], dict(other["c"]))
    try:
        table["absent"]["y"] += 1
    except KeyError as e:
        print("KeyError", e)
    plain = {}
    try:
        plain["x"] += 1
    except KeyError as e:
        print("plain KeyError", e)


main()
'''

COUNTER_SOURCES = r'''from collections import Counter


class Box:
    def __init__(self):
        self.c = Counter()


def bump(c, k, n):
    c[k] += n
    return c


def make():
    return Counter()


def main():
    c = Counter()
    bump(c, "a", 1)
    bump(c, "a", 2)
    bump(c, "b", -3)
    print(dict(c), c["a"], c["b"], c["zz"], len(c))
    xs = [Counter(), Counter()]
    xs[0]["x"] += 1
    xs[1]["q"] += 7
    print(dict(xs[0]), dict(xs[1]))
    box = Box()
    box.c["p"] += 7
    box.c["p"] += 1
    print(dict(box.c), box.c["p"])
    alias = c
    alias["a"] += 10
    print(dict(c), c["a"])
    r = make()
    r["m"] += 2
    print(dict(r), r["m"])
    nested = {"a": {"b": Counter()}}
    nested["a"]["b"]["k"] += 1
    nested["a"]["b"]["k"] += 1
    print(dict(nested["a"]["b"]), nested["a"]["b"]["k"])
    mixed = Counter()
    mixed[3] += 1
    mixed[(1, 2)] += 2
    mixed[True] += 4
    mixed["s"] += 8
    print(mixed[3], mixed[(1, 2)], mixed[True], mixed["s"], mixed[99], dict(mixed))
    empty = Counter()
    print(empty["nope"], len(empty), bool(empty))
    empty["nope"] += 1
    print(empty["nope"], len(empty), bool(empty))
    existing = Counter("aab")
    inc = 3
    existing["a"] += inc
    existing["b"] += inc
    existing["c"] += inc
    print(dict(existing), existing["a"], existing["b"], existing["c"])
    d = {"inc": 2}
    c["from_dict"] += d["inc"]
    c["from_list"] += xs[0]["x"]
    c["from_attr"] += box.c["p"]
    print(dict(c))


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


class Pre98Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-pre98-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_counter_missing_through_dict_value(self):
        self.check('counter_dict_value', COUNTER_DICT_VALUE)

    def test_counter_missing_from_every_source(self):
        self.check('counter_sources', COUNTER_SOURCES)


if __name__ == '__main__':
    unittest.main()
