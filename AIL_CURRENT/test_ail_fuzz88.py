"""Differential round 88: a dict comprehension built into its target before it was evaluated.

Found with small programs compared against CPython on both builds.

iterlower.py rewrites `d = {K: V for ...}` into `d = {}` followed by loops that fill `d`.
CPython evaluates the whole comprehension first and only then binds `d`, so a comprehension
that reads the old value (`d = {k: d[k] * 10 for k in d}`, `{k: v for k, v in d.items()}`,
`d.get(k, 0)`) must see the previous dict. The rewrite emptied it first, so the typed build
printed an empty/partial result or died with a key error.

The rewrite now leaves a self-reading comprehension alone, so the ordinary path evaluates its
value before assigning the target. The programs below keep the shapes compared with CPython on
both builds: reads of the old dict through items()/subscript/get(), duplicate keys keeping the
last value, conditionals, nested loops, negative and empty results, and a shadowing target name.
A comprehension that raises still leaves its partial dict on the typed path (a separate,
pre-existing difference reported with this change, not fixed here).
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

OLD_VALUE = r'''def main() -> None:
    d = {1: 10, 2: 20, 3: 30}
    d = {k: v + 1 for k, v in d.items()}
    print(len(d), d[1], d[2], d[3])
    d = {k: d[k] * 10 for k in d}
    print(len(d), d[1], d[2], d[3])
    d = {k: d.get(k, 0) + 5 for k in [1, 2, 4]}
    print(len(d), d[1], d[2], d[4])
    d = {k: d[k] for k in d if k > 1}
    print(len(d), d[2], d[4])
    print("done")


main()
'''

SHADOW_TARGET = r'''def main() -> None:
    d = {1: 10, 2: 20}
    d = {d: d for d in range(3)}
    print(len(d), d[0], d[1], d[2])
    print("done")


main()
'''

DUPLICATE_CONDITIONAL_NESTED = r'''def main() -> None:
    d = {x % 2: x for x in range(7) if x % 3 != 0}
    print(len(d), d[0], d[1])
    d = {x % 2: x for x in range(7) if x < 0}
    print(len(d))
    d = {x // 2: x for x in [-3, -2, -1, 0, 1, 2, 3]}
    print(len(d), d[-2], d[-1], d[0], d[1])
    d = {i: i + j for i in range(3) for j in range(3) if i != j}
    print(len(d), d[0], d[1], d[2])
    d = {k: v for k, v in [(1, 10), (2, 20), (1, 30)]}
    print(len(d), d[1], d[2])
    print("done")


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


class Fuzz88Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz88-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_old_value_from_items_subscript_get(self):
        self.check('old_value', OLD_VALUE)

    def test_target_name_shadowed_by_loop_variable(self):
        self.check('shadow_target', SHADOW_TARGET)

    def test_duplicate_conditional_and_nested_loops(self):
        self.check('dup_cond_nested', DUPLICATE_CONDITIONAL_NESTED)


if __name__ == '__main__':
    unittest.main()
