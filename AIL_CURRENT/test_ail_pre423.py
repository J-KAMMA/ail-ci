"""pre423: a statically short-circuited deferred read in a class annotation matches CPython.

pre410 stopped a lambda body or generator-expression element in a class-body annotation from
being treated as an immediate read, but every branch of a conditional expression and every
operand of ``and``/``or`` still counted.  ``class C: x: ((lambda: C)() if False else 1) = 1``
and ``x: (0 and (lambda: C)()) = 1`` were therefore refused although CPython never evaluates the
deferred read, so the annotation and the class body run normally.  The read now follows the
statically known truth value of an ``if`` expression and of ``and``/``or`` operands, including
empty containers; an unknown condition keeps the conservative refusal.  A literal containing an
unpacking (``[*()]``, ``(*(),)``, ``{*()}``, ``{**{}}``) can be empty at run time, so its truth is
unknown and the read stays refused.
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


MATCHING = {
    'if_false_lambda': annotated('(lambda: C)() if False else 1'),
    'if_false_genexp': annotated('list(C for _ in range(1)) if False else 1'),
    'nested_if_false': annotated('(lambda: C)() if False else ((lambda: C)() if False else 1)'),
    'and_zero': annotated('0 and (lambda: C)()'),
    'and_empty_list': annotated('[] and (lambda: C)()'),
    'and_empty_dict': annotated('{} and (lambda: C)()'),
    'and_none': annotated('None and (lambda: C)()'),
    'and_empty_str': annotated('"" and (lambda: C)()'),
    'or_one': annotated('1 or (lambda: C)()'),
    'or_negative': annotated('-1 or (lambda: C)()'),
    'or_list': annotated('[1] or (lambda: C)()'),
    'or_dict': annotated('{1: 2} or (lambda: C)()'),
    'or_str': annotated('"x" or (lambda: C)()'),
    'mixed_chain': annotated('(0 and (lambda: C)()) or (1 if True else (lambda: C)())'),
    'and_false_genexp': annotated('0 and list(C for _ in range(1))'),
    'or_nested_star_list': annotated('[[*()]] or (lambda: C)()'),
    'no_annotation_read': 'class C:\n    x: int = 1\nprint(C.x)\n',
}

REFUSED = {
    'if_true_lambda': annotated('(lambda: C)() if True else 1'),
    'if_true_genexp': annotated('list(C for _ in range(1)) if True else 1'),
    'and_one_lambda': annotated('1 and (lambda: C)()'),
    'and_true_genexp': annotated('[1] and list(C for _ in range(1))'),
    'or_zero_lambda': annotated('0 or (lambda: C)()'),
    'or_empty_list': annotated('[] or (lambda: C)()'),
    'or_none_genexp': annotated('None or list(C for _ in range(1))'),
    'nested_live': annotated('(lambda: C)() if True else ((lambda: C)() if False else 1)'),
    'unknown_condition': 'flag = False\n' + annotated('(lambda: C)() if flag else 1'),
    'or_star_list': annotated('[*()] or (lambda: C)()'),
    'or_star_tuple': annotated('(*(),) or (lambda: C)()'),
    'or_star_set': annotated('{*()} or (lambda: C)()'),
    'or_star_dict': annotated('{**{}} or (lambda: C)()'),
    'if_star_list': annotated('1 if [*()] else (lambda: C)()'),
    'if_star_tuple': annotated('1 if (*(),) else (lambda: C)()'),
    'if_star_dict': annotated('1 if {**{}} else (lambda: C)()'),
    'notif_star_list': annotated('(lambda: C)() if (not [*()]) else 1'),
    'notif_star_dict': annotated('(lambda: C)() if (not {**{}}) else 1'),
    'or_star_nonempty_list': annotated('[*[1]] or (lambda: C)()'),
    'or_star_nonempty_dict': annotated('{**{1: 2}} or (lambda: C)()'),
    'or_star_mixed_dict': annotated('{1: 2, **{}} or (lambda: C)()'),
}


class Pre423Tests(unittest.TestCase):
    def test_statically_dead_reads_match_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre423-') as directory:
            for slug, text in MATCHING.items():
                want = cpython(directory, slug, text)
                for general in (True, False):
                    exe, built = build(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                    self.assertEqual(built.returncode, 0, (slug, general, built.stdout + built.stderr))
                    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                    self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0],
                                     (slug, general, got.stderr[-800:]))
                    self.assertEqual(got.returncode, want[1], (slug, general, got.stderr[-800:]))

    def test_live_or_unknown_reads_are_refused(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre423-') as directory:
            for slug, text in REFUSED.items():
                for general in (True, False):
                    _, built = build(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                    output = built.stdout + built.stderr
                    self.assertNotEqual(built.returncode, 0, (slug, general, output[-1200:]))
                    self.assertIn(MESSAGE, output, (slug, general, output[-1200:]))


if __name__ == '__main__':
    unittest.main()
