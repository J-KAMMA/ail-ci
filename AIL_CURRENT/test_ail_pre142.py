"""pre142: `next()` of a saved generator expression is refused by name.

Both emitters materialise a generator expression as an eager list (there is no
lazy generator object), so `g = (x * 2 for x in [1, 2, 3]); next(g)` passed a
list to the runtime's iterator dispatcher and died with an internal error
("iterator: unknown kind") on both builds -- the first item a reviewer of
job pre116 recorded as pre-existing (its worker had fixed only the raising
shape, by refusal).  The direct shape `next(x for x in xs)` is lowered to a
real iterator and still matches CPython, and a saved genexpr consumed by
`for`/`list`/`sum` is unchanged.

`ail_chatgpt._check_saved_genexpr_next` now refuses `next()` when its argument
is a generator expression that was saved, following the value through plain
assignments, aliases, list items, attributes, dict values, returns and
parameters.  Every program below is built on both builds: the refused ones must
name the construct, the controls must print what CPython prints.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REFUSAL = 'next() of a saved generator expression is not in the subset'

RECORDED = '''def main():
    g = (x * 2 for x in [1, 2, 3])
    print(next(g))
    print(next(g))
    print(list(g))


main()
'''

ROUTES = [
    ('alias', '''def main():
    g = (x for x in [1, 2])
    h = g
    print(next(h))


main()
'''),
    ('argument', '''def first(it):
    return next(it)


def main():
    g = (x * 3 for x in [1, 2])
    print(first(g))


main()
'''),
    ('list_item', '''def main():
    gs = [(x for x in [1, 2])]
    print(next(gs[0]))


main()
'''),
    ('attribute', '''class Holder:
    def __init__(self):
        self.g = None


def main():
    h = Holder()
    h.g = (x for x in [1, 2])
    print(next(h.g))


main()
'''),
    ('dict_value', '''def main():
    d = {"a": (x for x in [1, 2])}
    print(next(d["a"]))


main()
'''),
    ('returned', '''def make():
    return (x for x in [1, 2])


def main():
    print(next(make()))


main()
'''),
    ('default', '''def main():
    g = (x for x in [])
    print(next(g, 9))


main()
'''),
    ('wrapper', '''def first(it):
    return next(it)


def wrapper(seq):
    return first(seq)


def main():
    print(wrapper(x for x in [5, 6]))


main()
'''),
    ('holder_param', '''def first(gs):
    return next(gs[0])


def main():
    gs = [(x for x in [1, 2])]
    print(first(gs))


main()
'''),
]

# The direct shape is a real iterator on both builds; the rest are controls that
# do not call next() at all and must keep matching CPython (no new refusal).
DIRECT = '''def main():
    print(next(x for x in [1, 2]))
    print(next(x * 2 for x in [3, 4]))


main()
'''

IMMEDIATE = '''def main():
    print(sum(x for x in [1, 2, 3]))
    print(list(x + 1 for x in range(4)))
    print(max(x for x in [3, 1, 2]))


main()
'''

SAVED_CONSUMED = '''def saved():
    g = (x + 1 for x in [1, 2, 3])
    total = 0
    for v in g:
        total += v
    return total


def main():
    print(saved())
    h = (x for x in [])
    print(list(h))


main()
'''

UNRELATED = '''def saved():
    g = (x for x in [1, 2])
    return list(g)


def other():
    it = iter([7, 8])
    return next(it)


def main():
    print(saved())
    print(other())


main()
'''


def _cpython(directory, slug, text):
    src = Path(directory) / (slug + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def _build(directory, slug, text, general):
    src = Path(directory) / (slug + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + slug)
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
        return None, built.stdout + built.stderr
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return got.stdout.replace(b'\r\n', b'\n'), got.returncode


class Pre142Tests(unittest.TestCase):
    def refused(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre142-') as directory:
            for general in (True, False):
                got, output = _build(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                     text, general)
                self.assertIsNone(got, 'built despite the refusal (general=%s):\n%s'
                                  % (general, text))
                self.assertIn(REFUSAL, output, 'wrong refusal (general=%s):\n%s'
                              % (general, output))

    def matches(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre142-') as directory:
            want, rc = _cpython(directory, slug, text)
            for general in (True, False):
                got = _build(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertEqual(got, (want, rc), 'general=%s:\n%s' % (general, text))

    def test_recorded_case_is_refused(self):
        self.refused('recorded', RECORDED)

    def test_routes_are_refused(self):
        for slug, text in ROUTES:
            with self.subTest(route=slug):
                self.refused(slug, text)

    def test_direct_next_matches(self):
        self.matches('direct', DIRECT)

    def test_immediate_consumers_match(self):
        self.matches('immediate', IMMEDIATE)

    def test_saved_genexpr_without_next_matches(self):
        self.matches('saved_consumed', SAVED_CONSUMED)

    def test_unrelated_next_is_not_refused(self):
        self.matches('unrelated', UNRELATED)


if __name__ == '__main__':
    unittest.main()
