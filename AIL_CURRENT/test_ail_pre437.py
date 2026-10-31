"""pre437: a class annotation that calls a walrus-bound lambda reads the class name.

Pre-existing on both builds: ``class C: x: ((f := (lambda: C)) and f()) = 1`` compiled and
printed 1, where CPython evaluates the annotation while the class body runs, calls the lambda
and raises ``NameError`` because ``C`` is not bound yet.  The annotation reader treated the
lambda body as deferred without following the name bound by the assignment expression, so the
call through ``f`` never ran it.  A name bound by ``:=`` is now resolved to the lambda or
generator it names, and a later call, ``__call__`` access, subscript of a literal aggregate or
known-consumer iteration through that name runs the deferred part.  A lambda argument to an
immediately called lambda is bound to its parameter.  A lambda or generator expression is also
truthy, so a live ``or`` operand returns it without evaluating the rest.  Unused bindings,
statically dead branches and shadowing parameters keep CPython's acceptance.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')
MESSAGE = 'a class body annotation reads the class name C before it is bound'


def cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1', PYTHONWARNINGS='ignore'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def build(directory, name, text, general):
    src = Path(directory) / (name + '.py')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    return exe, subprocess.run([sys.executable, '-B', CHATGPT, 'compile', src.name,
                                '--syntax', 'python', '-o', exe.name], cwd=directory,
                               capture_output=True, text=True, timeout=900, env=env)


def annotated(expression):
    return 'class C:\n    x: (%s) = 1\nprint(C.x)\n' % expression


def callable_annotation(expression):
    return 'class C:\n    x: (%s) = 1\nprint(callable(C.x))\n' % expression


MATCHING = {
    'alias_no_call': callable_annotation('f := (lambda: C)'),
    'alias_or_returns_lambda': callable_annotation('(f := (lambda: C)) or f()'),
    'alias_dead_if': annotated('1 if False else (f := (lambda: C))'),
    'alias_dead_and': annotated('0 and (f := (lambda: C))'),
    'alias_shadow_param': annotated('(f := (lambda: C)) and (lambda C: C)(1)'),
    'alias_shadow_body': annotated('(f := (lambda C: C)) and f(3)'),
    'alias_shadow_call': annotated('(f := (lambda: C)) and (lambda f: f)(5)'),
    'alias_container_no_call': annotated('(l := [(lambda: C)]) and 1'),
    'alias_genexp_unused': annotated('(g := (y for y in [1] if C)) and 1'),
    'alias_map_empty': annotated('(f := (lambda: C)) and list(map(f, []))'),
    'alias_bool_use': annotated('(f := (lambda: C)) and bool(f)'),
    'alias_nested_lambda': callable_annotation('(f := (lambda: C)) and (lambda: f)'),
    'alias_default_arg': annotated('(f := (lambda: C)) and (lambda d: d)(7)'),
    'lambda_truthy_or': callable_annotation('(lambda: C) or (lambda: C)()'),
    'genexp_truthy_or': callable_annotation(
        '(y for y in [1] if C) or list(y for y in [1] if C)'),
    'genexp_dead_or': annotated('1 or (g := (y for y in [1] if C)) or list(g)'),
    'no_alias': 'class C:\n    x: int = 1\nprint(C.x)\n',
}

REFUSED = {
    'alias_and_call': annotated('(f := (lambda: C)) and f()'),
    'alias_paren_call': annotated('(f := (lambda: C)) and (f)()'),
    'alias_chain': annotated('(f := (g := (lambda: C))) and g()'),
    'alias_list_item': annotated('(l := [(lambda: C)]) and l[0]()'),
    'alias_tuple_item': annotated('(t := ((lambda: C),)) and t[0]()'),
    'alias_dict_value': annotated('(d := {"k": (lambda: C)}) and d["k"]()'),
    'alias_dunder_call': annotated('(f := (lambda: C)) and f.__call__()'),
    'alias_as_argument': annotated('(f := (lambda: C)) and (lambda g: g())(f)'),
    'alias_body_read': annotated('(f := (lambda d: C)) and f(3)'),
    'alias_consumer_genexp': annotated('(g := (y for y in [1] if C)) and list(g)'),
    'alias_star_genexp': annotated('(g := (y for y in [1] if C)) and [*g]'),
    'alias_default_reads': annotated('(f := (lambda d=C: d)) and 1'),
}


class Pre437Tests(unittest.TestCase):
    def test_alias_dead_or_shadowed_reads_match_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre437-') as directory:
            for slug, text in MATCHING.items():
                want = cpython(directory, slug, text)
                for general in (True, False):
                    exe, built = build(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                    self.assertEqual(built.returncode, 0, (slug, general, built.stdout + built.stderr))
                    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                    self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0],
                                     (slug, general, got.stderr[-800:]))
                    self.assertEqual(got.returncode, want[1], (slug, general, got.stderr[-800:]))

    def test_live_alias_reads_are_refused(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre437-') as directory:
            for slug, text in REFUSED.items():
                for general in (True, False):
                    _, built = build(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                    output = built.stdout + built.stderr
                    self.assertNotEqual(built.returncode, 0, (slug, general, output[-1200:]))
                    self.assertIn(MESSAGE, output, (slug, general, output[-1200:]))


if __name__ == '__main__':
    unittest.main()
