"""cov50: nested generator expressions whose every level is read by a full-consumer call.

The corpus profile found three programs refused only on the general path's blunt nested-
generator rule (a nested generator expression was refused even when both levels are consumed
by a call that reads every element, like ``" ".join("".join(...) for row in rows)``).  Such a
chain is evaluated at one point, so the existing eager lowering keeps CPython's order; the
general path now accepts it on both builds.  A nested generator that can stop early (``any``,
``all``, ``next``), is saved as a value, is passed to a user function, or is walked by a
``for`` loop that can break keeps the named refusal, because there the eager list would run
code CPython has not run yet.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')

MATCHING = {
    'join': r"""def mark(x: int) -> str:
    print("mark", x)
    return str(x)


def main() -> None:
    rows = [[1, -2], [], [3, 4, 5], [0]]
    print("|".join("-".join(mark(v) for v in row) for row in rows))
    print(",".join("".join(mark(v * 10) for v in row) for row in rows if row))


main()
""",
    'sum_min_max': r"""def f(x: int) -> int:
    print("f", x)
    return x * x


def main() -> None:
    rows = [[1, 2], [], [3, 4, 5]]
    print(sum(sum(f(v) for v in row) for row in rows))
    print(max(max(f(v) for v in row) for row in rows if row))
    print(min(min(f(v) for v in row) for row in rows if row))
    print(sum(sum(v + 0.5 for v in row) for row in rows))


main()
""",
    'containers': r"""def main() -> None:
    rows = [[3, 1], [], [2, 2, 1]]
    print(list(list(v * 2 for v in row) for row in rows))
    print(sorted(sorted(row) for row in rows))
    cube = [[[1, 2], [3]], [[4], []]]
    print(";".join(",".join("-".join(str(v) for v in row) for row in plane) for plane in cube))


main()
""",
    'raise': r"""def f(x: int) -> int:
    print("f", x)
    if x == 3:
        raise ValueError("boom")
    return x


def main() -> None:
    rows = [[1, 2], [3, 4]]
    try:
        print(",".join("-".join(str(f(v)) for v in row) for row in rows))
    except ValueError as e:
        print("caught", e)
    try:
        print(sum(sum(f(v) for v in row) for row in rows))
    except ValueError as e:
        print("caught2", e)


main()
""",
    'routes': r"""class Box:
    def __init__(self, rows: list[list[int]]) -> None:
        self.rows = rows


def total(rows: list[list[int]]) -> int:
    return sum(sum(v for v in row) for row in rows)


def main() -> None:
    a = [[1, 2], [3]]
    b = Box([[4], [5, 6]])
    data = {"rows": [[7, 8], [9]]}
    print(total(a))
    print("|".join("-".join(str(v) for v in row) for row in b.rows))
    print(total(data["rows"]))
    print(total([a[0], b.rows[1]]))
    print(total([data["rows"][1]]))


main()
""",
}

REFUSED = {
    'any_short_circuit': r"""def mark(x: int) -> int:
    print("mark", x)
    return x


def main() -> None:
    print(any(v > 1 for v in (mark(i) for i in [0, 1, 2])))


main()
""",
    'saved_value': r"""def main() -> None:
    xs = [1, 2, 3]
    g = (v for v in (w * 2 for w in xs))
    print("before")
    print(list(g))


main()
""",
    'for_break': r"""def main() -> None:
    xs = [1, 2, 3]
    for v in (w * 2 for w in (x for x in xs)):
        print(v)
        break


main()
""",
    'lazy_zip': r"""def main() -> None:
    xs = [1, 2, 3]
    print(list(zip((v for v in (w * 2 for w in xs)), xs)))


main()
""",
    'user_function': r"""def take(g) -> None:
    print(next(g))


def main() -> None:
    xs = [1, 2, 3]
    take(v for v in (w * 2 for w in xs))


main()
""",
}


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


class Cov50Tests(unittest.TestCase):
    def test_nested_generator_expressions_match_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-cov50-') as directory:
            for slug, text in MATCHING.items():
                want = cpython(directory, slug, text)
                for general in (True, False):
                    exe, built = build(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                    self.assertEqual(built.returncode, 0, (slug, general, built.stdout + built.stderr))
                    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                    self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0],
                                     (slug, general, got.stderr[-800:]))
                    self.assertEqual(got.returncode, want[1], (slug, general, got.stderr[-800:]))

    def test_early_stop_or_saved_nested_generator_is_refused(self):
        with tempfile.TemporaryDirectory(prefix='ail-cov50-') as directory:
            for slug, text in REFUSED.items():
                for general in (True, False):
                    _, built = build(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                    output = built.stdout + built.stderr
                    self.assertEqual(built.returncode, 3, (slug, general, output[-1200:]))
                    self.assertIn('not in the subset', output, (slug, general, output[-1200:]))
                    self.assertIn('generator expression', output, (slug, general, output[-1200:]))


if __name__ == '__main__':
    unittest.main()
