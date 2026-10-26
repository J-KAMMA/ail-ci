"""pre124: module-scope annotations are evaluated like CPython's.

A module-level `target: annotation` (with or without a value) evaluates its target and annotation
in CPython.  The typed and general paths dropped the annotation, and a bare annotation dropped the
target too: `touch(b).x: ann()` never called `ann` and `xs[touch(i)]: ann()` never evaluated `xs`
or `i`.  The Python surface now keeps those evaluations in order, also under
`from __future__ import annotations` (where CPython evaluates the target only).  Static type
expressions (`int`, `list[int]`, `A | None`) stay unevaluated, as before.

Each program is built with both the general path and the default build and compared with CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

TARGETS = r'''class Box:
    x = 0


b = Box()
order = []


def touch(obj, tag):
    order.append('target:' + tag)
    return obj


def ann(tag):
    order.append('ann:' + tag)
    return 'A' + tag


touch(b, 'attr').x: ann('attr')
xs = [0]
xs[touch(0, 'sub')]: ann('sub')
xs[-1]: ann('neg')
xs[()]: ann('empty')
print(order)
print('done')
'''

PROPERTY_AND_SLICES = r'''class Box:
    def __init__(self):
        self.log = []

    @property
    def x(self):
        self.log.append('get x')
        return 1


order = []


def mark(tag):
    order.append(tag)
    return 1


def ann():
    order.append('ann')
    return 'T'


b = Box()
b.x: ann()
print(order, b.log)
xs = [[0, 1, 2], [3, 4, 5]]
xs[mark('lo'):mark('hi'):mark('step')]: ann()
xs[mark('a'), mark('lo'):mark('hi')]: ann()
xs[()]: ann()
print(order)
'''

SOURCES = r'''class Box:
    def __init__(self):
        self.fn = None


order = []


def make(tag):
    order.append('make:' + tag)

    def ann():
        order.append('ann:' + tag)
        return 'A' + tag
    return ann


def use(fn):
    return fn


def main():
    items = [make('list')]
    handlers = {'k': make('dict')}
    box = Box()
    box.fn = make('attr')
    xs = [0, 1]
    ys = [0, 1]
    zs = [0, 1]
    ws = [0, 1]
    items[0]()                 # a call, not an annotation: control
    xs[0]: items[0]()
    ys[1]: box.fn()
    zs[0]: handlers['k']()
    ws[0]: use(make('arg'))()
    print(order)


main()
'''

STATIC_AND_VALUES = r'''order = []


def val(tag):
    order.append('val:' + tag)
    return tag


def ann(tag):
    order.append('ann:' + tag)
    return 'A' + tag


x: ann('name') = val('name')
o = {}
o['a']: ann('item') = val('item')


class Box:
    pass


b = Box()
b.a: ann('attr') = val('attr')
p: int
q: list[int]
r: dict[str, int]
s: int | None
print(order)
print(x, sorted(o), b.a)
'''

FUTURE = r'''from __future__ import annotations

order = []


class Box:
    x = 0


b = Box()


def touch(obj, tag):
    order.append('target:' + tag)
    return obj


def ann(tag):
    order.append('ann:' + tag)
    return 'A' + tag


x: ann('name')
touch(b, 'attr').x: ann('attr')
xs = [0]
xs[touch(0, 'sub')]: ann('sub')
y: ann('value') = 5
print(order)
print('done')
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


class Pre124Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-pre124-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_bare_module_targets(self):
        self.check('bare_targets', TARGETS)

    def test_property_and_slices(self):
        self.check('property_slices', PROPERTY_AND_SLICES)

    def test_annotation_sources(self):
        self.check('annotation_sources', SOURCES)

    def test_static_annotations_and_values(self):
        self.check('static_values', STATIC_AND_VALUES)

    def test_future_annotations_evaluate_the_target_only(self):
        self.check('future_annotations', FUTURE)


if __name__ == '__main__':
    unittest.main()
