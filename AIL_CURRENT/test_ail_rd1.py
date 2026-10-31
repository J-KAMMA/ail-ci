"""rd1: the refusals for `exec(...)`, `async def` and the `--strict` big-integer gate name the
position, like every other refusal, and say what to write instead.

The tutorial (ail-ci#222) hit three refusals that printed no file:line: an unbound `exec(...)`, an
`async def`, and a program whose exact integer leaves int64 under `--strict`.  Each now prints
`path:line:col: not in the subset: ...` plus a `  write instead: ` line on both builds (the default
and `AIL_UNIFIED_FORCE=1`); `--strict` still prints its blocker list for a program with top-level
`def`s, and each blocker names its own `path:line:col`.  Programs that use exact integers without
`--strict` keep matching CPython on both builds.
"""
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')


def cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1', PYTHONWARNINGS='ignore'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def compile_program(directory, name, text, general, strict=False):
    src = Path(directory) / (name + '.py')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name)
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    argv = [sys.executable, '-B', CHATGPT, 'compile', src.name, '--syntax', 'python',
            '-o', exe.name]
    if strict:
        argv.append('--strict')
    return exe, subprocess.run(argv, cwd=directory, capture_output=True, text=True, timeout=900,
                               env=env)


# (slug, source, "line:col" the refusal must name, phrases the message must contain)
REFUSALS = [
    ('exec_toplevel', 'exec("print(1)")\n', '1:1',
     ['exec() is not built', 'compiles the whole program ahead of time']),
    ('exec_in_def', 'def main():\n    exec("print(1)")\n\n\nmain()\n', '2:5', ['exec']),
    ('async_alone', 'async def f():\n    pass\n', '1:1',
     ['async def', 'no coroutines or event loop', 'an ordinary `def`']),
    ('async_in_script', 'async def f():\n    return 1\n\n\ndef main():\n    print(1)\n\n\nmain()\n',
     '1:1', ['async def', 'no coroutines or event loop', 'an ordinary `def`']),
]

# a whole program whose exact integer leaves int64: `--strict` must refuse it by position
BIG_STRICT = [
    ('big_pow', 'def main() -> int:\n    return 10 ** 30\n\n\nprint(main())\n', '2:5'),
    ('big_toplevel', 'print(10 ** 30)\n', '1:1'),
    ('big_negative', 'print(-9223372036854775809)\n', '1:1'),
    ('big_arg', 'def f(x):\n    return x * x\n\n\nprint(f(10 ** 30))\n', '5:1'),
    ('big_list', 'xs = [10 ** 30]\nprint(xs[0])\n', '1:1'),
    ('big_dict', 'd = {"v": 10 ** 30}\nprint(d["v"])\n', '1:1'),
    ('big_attr', 'class Box:\n    def __init__(self):\n        self.v = 10 ** 30\n\n\nprint(Box().v)\n',
     '3:9'),
]

# exact integers are the general path's job; without `--strict` these match CPython
MATCHING = {
    'big_literal': 'print(9223372036854775808)\n',
    'big_literal_in_def': 'def main() -> int:\n    x = 9223372036854775808\n    return x\n\n\nprint(main())\n',
    'big_pow': 'def main() -> int:\n    return 10 ** 30\n\n\nprint(main())\n',
    'big_pow_toplevel': 'print(10 ** 30)\n',
    'big_inrange': 'def main() -> int:\n    return 2 ** 62 - 1\n\n\nprint(main())\n',
}


class Rd1Tests(unittest.TestCase):
    def test_refusals_name_position_and_rewrite(self):
        for slug, source, where, phrases in REFUSALS:
            for general in (True, False):
                for strict in (False, True):
                    with self.subTest(slug=slug, general=general, strict=strict), \
                            tempfile.TemporaryDirectory() as directory:
                        exe, built = compile_program(directory, slug, source, general, strict)
                        text = built.stderr
                        self.assertIn(built.returncode, (2, 3), text)
                        self.assertFalse(exe.exists(), (slug, general, strict, text))
                        self.assertNotIn('usage:', text)
                        lines = [line for line in text.splitlines() if line and not line.startswith('note:')]
                        if lines[0].startswith('strict: '):
                            rows = [line for line in lines if re.match(r'^\d+\. ', line)]
                            self.assertTrue(rows, text)
                            self.assertTrue(rows[0].split('. ', 1)[1].startswith(
                                '%s.py:%s' % (slug, where)), text)
                        else:
                            self.assertRegex(lines[0], r'^%s\.py:\d+:\d+: not in the subset: ' % re.escape(slug),
                                             text)
                            self.assertTrue(lines[0].startswith('%s.py:%s' % (slug, where)), text)
                            self.assertLessEqual(len(lines), 3, text)
                        self.assertTrue(any(line.strip().startswith('write instead: ') for line in lines),
                                        text)
                        for phrase in phrases:
                            self.assertIn(phrase, text)

    def test_strict_big_integer_is_refused_by_position(self):
        for slug, source, where in BIG_STRICT:
            with self.subTest(slug=slug), tempfile.TemporaryDirectory() as directory:
                exe, built = compile_program(directory, slug, source, general=False, strict=True)
                text = built.stderr
                self.assertEqual(built.returncode, 3, text)
                self.assertFalse(exe.exists(), text)
                lines = [line for line in text.splitlines() if line and not line.startswith('note:')]
                self.assertRegex(lines[0], r'^%s\.py:\d+:\d+: not in the subset: ' % re.escape(slug), text)
                self.assertTrue(lines[0].startswith('%s.py:%s' % (slug, where)), text)
                self.assertIn('beyond int64', text)
                self.assertTrue(any(line.strip().startswith('write instead: ') and 'without --strict' in line
                                    for line in lines), text)
            with self.subTest(slug=slug, general=True), tempfile.TemporaryDirectory() as directory:
                # --strict plus an explicitly requested general path refuses before the gate (the
                # pre-existing configuration refusal); what matters is that nothing is built
                exe, built = compile_program(directory, slug, source, general=True, strict=True)
                self.assertEqual(built.returncode, 3, built.stderr)
                self.assertFalse(exe.exists(), built.stderr)

    def test_exact_integers_match_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-rd1-') as directory:
            for slug, text in MATCHING.items():
                want = cpython(directory, slug, text)
                for general in (True, False):
                    exe, built = compile_program(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                 text, general)
                    self.assertEqual(built.returncode, 0, (slug, general, built.stdout + built.stderr))
                    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                    self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0],
                                     (slug, general, got.stderr[-800:]))
                    self.assertEqual(got.returncode, want[1], (slug, general, got.stderr[-800:]))


if __name__ == '__main__':
    unittest.main()
