"""Pre-254: a module-level bare annotation with a starred subscript target is refused.

CPython rejects ``xs[*a]: ann()`` with ``SyntaxError: can't use starred expression here``.
AIL's module bare-annotation rewrite used to leave a directly starred subscript target as
written, and the lowerers dropped the value-less annotation, so the program built and ran on
both paths.  The rewrite now refuses the construct by name at compile time, with exit 2 on both
builds.  Starred expressions in load position (``xs[[*a]]``, ``xs[ys[*a]]``, ``xs[f(*a)]``) and
the annotated-assignment form with a value stay as they were.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

REFUSED = {
    'direct': '''xs = [1, 2]
a = [0]


def ann():
    print("ann")


xs[*a]: ann()
print("done")
''',
    'trailing_comma': '''xs = [1, 2]
a = [0]


def ann():
    print("ann")


xs[*a,]: ann()
print("done")
''',
    'mixed': '''xs = [1, 2]
a = [0]
b = [1]


def ann():
    print("ann")


xs[0, *a, *b]: ann()
print("done")
''',
    'double_star': '''xs = [1, 2]
a = [0]
b = [1]


def ann():
    print("ann")


xs[*a, *b]: ann()
print("done")
''',
    'nested_tuple': '''xs = [1, 2]
a = [0]


def ann():
    print("ann")


xs[((*a,),)]: ann()
print("done")
''',
    'future': '''from __future__ import annotations

xs = [1, 2]
a = [0]


def ann():
    print("ann")


xs[*a]: ann()
print("done")
''',
    'attribute_base': '''class Holder:
    pass


holder = Holder()
holder.xs = [1, 2]
a = [0]


def ann():
    print("ann")


holder.xs[*a]: ann()
print("done")
''',
    'list_item_base': '''rows = [[1, 2]]
a = [0]


def ann():
    print("ann")


rows[0][*a]: ann()
print("done")
''',
    'dict_value_base': '''table = {"xs": [1, 2]}
a = [0]


def ann():
    print("ann")


table["xs"][*a]: ann()
print("done")
''',
    'argument_base': '''def make():
    return [1, 2]


a = [0]


def ann():
    print("ann")


make()[*a]: ann()
print("done")
''',
    'empty_star': '''xs = [1, 2]
a = []


def ann():
    print("ann")


xs[*a]: ann()
print("done")
''',
}

VALID = {
    'list_display_star': '''xs = {(0,): "zero"}
a = [0]


def ann():
    print("ann")


xs[[*a]]: ann()
print("done")
''',
    'dict_display_star': '''xs = {(0,): "zero"}
a = [0]


def ann():
    print("ann")


xs[{*a}]: ann()
print("done")
''',
    'call_star': '''xs = {(0,): "zero"}
a = [0]


def key(*values):
    return values


def ann():
    print("ann")


xs[key(*a)]: ann()
print("done")
''',
    'nested_subscript_star': '''ys = {(0,): 0}
xs = {0: "zero"}
a = [0]


def ann():
    print("ann")


xs[ys[*a]]: ann()
print("done")
''',
    'ifexp_star': '''xs = {(0,): "zero"}
a = [0]
flag = True


def ann():
    print("ann")


xs[(*a,) if flag else 0]: ann()
print("done")
''',
    'binop_star': '''xs = {(0,): "zero"}
a = [0]
tail = ()


def ann():
    print("ann")


xs[(*a,) + tail]: ann()
print("done")
''',
    'nested_tuple_no_star': '''xs = {(0,): "zero"}
a = 0


def ann():
    print("ann")


xs[((a,),)]: ann()
print("done")
''',
    'attribute_star_load': '''class Box:
    pass


box = Box()
xs = {(0,): box}
a = [0]


def ann():
    print("ann")


xs[*a].attr: ann()
print("done")
''',
    'with_value': '''xs = {(0,): 1}
a = [0]


def ann():
    print("ann")


xs[*a]: ann = 3
print(xs)
''',
    'with_value_nested': '''xs = {(0,): 1}
a = [0]


def ann():
    print("ann")


xs[((*a,),)]: ann = 3
print(xs)
''',
}


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


def _build(directory, name, text, general):
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
    return built, exe


def _run(directory, name, text, general):
    built, exe = _build(directory, name, text, general)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class Pre254Tests(unittest.TestCase):
    def refused(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre254-') as directory:
            want, want_rc, err = _cpython(directory, slug, text)
            self.assertNotEqual(want_rc, 0, err)
            self.assertIn(b"can't use starred expression here", err)
            for general in (True, False):
                name = '%s_%s' % (slug, 'g' if general else 'd')
                built, exe = _build(directory, name, text, general)
                output = built.stdout + built.stderr
                self.assertEqual(built.returncode, 2, '%s (general=%s)\n%s' % (slug, general, output[-3000:]))
                self.assertFalse(exe.exists(), '%s (general=%s) built an executable' % (slug, general))
                self.assertIn('a starred expression in an annotated assignment target', output,
                              '%s (general=%s)\n%s' % (slug, general, output[-3000:]))
                self.assertIn('not valid Python syntax', output,
                              '%s (general=%s)\n%s' % (slug, general, output[-3000:]))

    def matches(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre254-') as directory:
            want, want_rc, err = _cpython(directory, slug, text)
            self.assertEqual(want_rc, 0, err)
            for general in (True, False):
                got, build_err = _run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                      text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (slug, general, build_err))
                self.assertEqual(got, (want, want_rc), '%s (general=%s)\n%s' % (slug, general, build_err))

    def test_starred_bare_module_annotation_is_refused(self):
        for slug, text in REFUSED.items():
            self.refused(slug, text)

    def test_starred_load_positions_and_value_form_still_match(self):
        for slug, text in VALID.items():
            self.matches(slug, text)


if __name__ == '__main__':
    unittest.main()
