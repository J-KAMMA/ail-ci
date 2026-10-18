"""A `try` moved out of a loop (tryhoist.py): the hoisted build, the build without the rewrite and CPython agree.

Each program is compiled twice -- as is, and with AIL_NO_TRYHOIST=1 -- and run next to CPython; output and
exit status must match in all three. The programs are chosen so that a wrong hoist changes them: a pre-try
statement that raises something the handler catches, a handler that falls back into the loop, a handler
that reads a name only the loop assigns, a `continue`/`break` inside the hoisted body, recursion and a
handler that re-raises into an outer `try`. A second group checks which loops the rewrite touches.
"""
import ast
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'python' / 'pkg-v12'))
import tryhoist  # noqa: E402

CASES = {}


def case(name, hoisted):
    def register(source):
        CASES[name] = (source, hoisted)
        return source
    return register


case('while_return', True)('''
def f(n: int) -> int:
    xs: list[int] = [3, 1, 4, 1, 5, 9, 2, 6]
    i = 0
    total = 0
    while i < len(xs):
        k = xs[i]
        try:
            if k == n:
                raise ValueError("hit")
            total += k
            i += 1
        except ValueError:
            print("caught at", i, "total", total)
            return -1
    return total

def main() -> int:
    for n in range(11):
        print(n, f(n))
    return 0

main()
''')

case('continue_break_in_body', True)('''
def f(n: int) -> int:
    i = 0
    total = 0
    while i < 20:
        i += 1
        try:
            if i % 2 == 0:
                continue
            if i > n:
                break
            if i == 7:
                raise ValueError()
            total += i
        except ValueError:
            return -total
    return total

def main() -> int:
    for n in range(0, 22, 3):
        print(n, f(n))
    return 0

main()
''')

case('for_range', True)('''
def f(n: int) -> int:
    total = 0
    for i in range(10):
        try:
            if i == n:
                raise KeyError("x")
            total += i * i
        except KeyError:
            print("key at", i)
            return total
    return total

def main() -> int:
    for n in range(12):
        print(n, f(n))
    return 0

main()
''')

case('nested_loops_both', True)('''
def g(n: int) -> int:
    i = 0
    total = 0
    while i < 3:
        j = 0
        while j < 3:
            try:
                if i * 3 + j == n:
                    raise ValueError("v")
                total += i * 10 + j
                j += 1
            except ValueError:
                print("caught", n, total)
                return n
        i += 1
    return total

def main() -> int:
    for n in range(11):
        print(n, g(n))
    return 0

main()
''')

case('reraise_into_outer', True)('''
def inner(n: int) -> int:
    i = 0
    while i < 5:
        try:
            if i == n:
                raise ValueError("v")
            i += 1
        except ValueError:
            print("inner caught")
            raise
    return i

def f(n: int) -> int:
    try:
        return inner(n)
    except ValueError:
        return -9

def main() -> int:
    for n in range(7):
        print(n, f(n))
    return 0

main()
''')

case('callee_raises_other_type', True)('''
def deep(n: int, i: int) -> int:
    if i == n:
        raise IndexError("deep")
    return i

def f(n: int) -> int:
    total = 0
    try:
        i = 0
        while i < 6:
            try:
                total += deep(n, i)
                if i == 4:
                    raise ValueError()
                i += 1
            except ValueError:
                return 1000 + total
    except IndexError:
        return 2000 + total
    return total

def main() -> int:
    for n in range(8):
        print(n, f(n))
    return 0

main()
''')

case('recursion', True)('''
def walk(depth: int, limit: int) -> int:
    i = 0
    total = 0
    while i < 3:
        try:
            if depth < limit:
                total += walk(depth + 1, limit)
            elif i == 2:
                raise ValueError()
            total += 1
            i += 1
        except ValueError:
            return -depth
    return total

def main() -> int:
    for limit in range(5):
        print(limit, walk(0, limit))
    return 0

main()
''')

case('tuple_handler_unused_name', True)('''
def f(n: int) -> int:
    i = 0
    while i < 6:
        try:
            if i == n:
                raise KeyError("k")
            if i == n + 1:
                raise ValueError("v")
            i += 1
        except (KeyError, ValueError) as e:
            return i * 7
    return 0

def main() -> int:
    for n in range(8):
        print(n, f(n))
    return 0

main()
''')

# ---- shapes that must keep their try inside the loop

case('pre_statement_raises_caught_type', False)('''
def f(xs: list[int]) -> int:
    i = 0
    total = 0
    while i < 10:
        k = xs[i]
        try:
            total += k
            i += 1
        except IndexError:
            return -2
    return total

def main() -> int:
    print(f([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]))
    print(f([1, 2, 3]))
    return 0

main()
''')

case('handler_falls_through', False)('''
def f(n: int) -> int:
    i = 0
    total = 0
    while i < 6:
        try:
            if i == n:
                raise ValueError()
            total += i
        except ValueError:
            print("skip", i)
        i += 1
    return total

def main() -> int:
    for n in range(8):
        print(n, f(n))
    return 0

main()
''')

case('handler_continues', False)('''
def f(n: int) -> int:
    i = 0
    total = 0
    while i < 6:
        i += 1
        try:
            if i == n:
                raise ValueError()
            total += i
        except ValueError:
            total += 100
            continue
    return total

def main() -> int:
    for n in range(8):
        print(n, f(n))
    return 0

main()
''')

case('try_else', False)('''
def f(n: int) -> int:
    i = 0
    total = 0
    while i < 6:
        try:
            if i == n:
                raise ValueError()
        except ValueError:
            return -1
        else:
            total += 10
        i += 1
    return total

def main() -> int:
    for n in range(8):
        print(n, f(n))
    return 0

main()
''')

case('try_finally', False)('''
def f(n: int) -> int:
    i = 0
    total = 0
    while i < 6:
        try:
            if i == n:
                raise ValueError()
            total += 1
        except ValueError:
            return -1
        finally:
            total += 100
        i += 1
    return total

def main() -> int:
    for n in range(8):
        print(n, f(n))
    return 0

main()
''')

case('handler_reads_pre_assigned_name', True)('''
def f(n: int) -> int:
    i = 0
    while i < 6:
        k = i * 2
        try:
            if i == n:
                raise ValueError()
            i += 1
        except ValueError:
            return k
    return -1

def main() -> int:
    for n in range(8):
        print(n, f(n))
    return 0

main()
''')

case('call_in_pre', False)('''
def check(i: int, n: int) -> int:
    if i == n:
        raise ValueError("pre")
    return i

def f(n: int) -> int:
    i = 0
    total = 0
    while i < 6:
        k = check(i, n)
        try:
            total += k
            i += 1
        except IndexError:
            return -1
    return total

def main() -> int:
    print(f(99))
    print(f(3))
    return 0

main()
''')

case('two_tries_in_body', False)('''
def f(n: int) -> int:
    i = 0
    total = 0
    while i < 6:
        try:
            if i == n:
                raise ValueError()
        except ValueError:
            return -1
        try:
            total += i
        except KeyError:
            return -2
        i += 1
    return total

def main() -> int:
    for n in range(8):
        print(n, f(n))
    return 0

main()
''')


def pythons(source):
    return ast.parse(source.strip())


class TryHoistTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='ail-hoist-')
        cls.root = Path(cls.tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def build(self, name, source, rewrite):
        path = self.root / (name + '.py')
        path.write_text(source.strip() + '\n', encoding='utf8')
        exe = self.root / (name + ('-hoist' if rewrite else '-plain'))
        env = dict(os.environ, PYTHONUTF8='1')
        env.pop('AIL_NO_TRYHOIST', None)
        if not rewrite:
            env['AIL_NO_TRYHOIST'] = '1'
        result = subprocess.run([sys.executable, '-X', 'utf8', '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', str(path),
                                 '--syntax', 'python', '-o', str(exe)], capture_output=True, env=env, timeout=240)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        return exe

    def run_exe(self, exe):
        result = subprocess.run([str(exe)], capture_output=True, timeout=60)
        return result.returncode, result.stdout

    def oracle(self, name, source):
        path = self.root / (name + '.ref.py')
        path.write_text(source.strip() + '\n', encoding='utf8')
        result = subprocess.run([sys.executable, '-X', 'utf8', str(path)], capture_output=True, timeout=60)
        return result.returncode, result.stdout

    def test_rewrite_applies_where_it_should(self):
        for name, (source, hoisted) in CASES.items():
            with self.subTest(name):
                self.assertEqual(tryhoist.rewrite(pythons(source)), hoisted)

    def test_outer_loop_is_hoisted_again(self):
        tree = pythons('''
def g(n: int) -> int:
    i = 0
    while i < 3:
        j = 0
        while j < 3:
            try:
                if i == n:
                    raise ValueError()
                j += 1
            except ValueError:
                return n
        i += 1
    return 0

main()
''')
        self.assertTrue(tryhoist.rewrite(tree))
        loops = [node for node in ast.walk(tree) if isinstance(node, (ast.While, ast.For))]
        tries = [node for node in ast.walk(tree) if isinstance(node, ast.Try)]
        self.assertEqual(len(loops), 2)
        self.assertEqual(len(tries), 1)
        self.assertIsInstance(tree.body[0].body[-2], ast.Try)
        self.assertEqual(sum(isinstance(node, ast.While) for node in tree.body[0].body), 0)

    def test_names_that_could_hide_a_raise_are_refused(self):
        refused = {
            'caught_overflow': '''
def f(n: int) -> int:
    i = 0
    while i < 5:
        k = i + n
        try:
            i += 1
        except OverflowError:
            return -1
    return i
''',
            'shadowed_len': '''
def len(x: list[int]) -> int:
    raise ValueError("mine")

def f(xs: list[int]) -> int:
    i = 0
    while i < len(xs):
        try:
            i += 1
        except ValueError:
            return -1
    return i
''',
            'field_of_none_caught': '''
def f(n: int) -> int:
    i = 0
    while i < 5:
        k = n.val
        try:
            i += 1
        except RuntimeError:
            return -1
    return i
''',
            'unknown_handler_type': '''
def f(n: int) -> int:
    i = 0
    while i < 5:
        try:
            i += 1
        except Exception:
            return -1
    return i
''',
            'division_pre': '''
def f(n: int) -> int:
    i = 0
    while i < 5:
        k = 10 // n
        try:
            i += 1
        except ZeroDivisionError:
            return -1
    return i
''',
        }
        for name, source in refused.items():
            with self.subTest(name):
                self.assertFalse(tryhoist.rewrite(pythons(source)))

    def test_programs_agree_with_cpython_and_the_unrewritten_build(self):
        for name, (source, _) in CASES.items():
            with self.subTest(name):
                reference = self.oracle(name, source)
                plain = self.run_exe(self.build(name, source, False))
                hoisted = self.run_exe(self.build(name, source, True))
                self.assertEqual(plain, reference)
                self.assertEqual(hoisted, reference)

    def test_uncaught_index_error_from_the_loop_header_still_escapes(self):
        source = '''
def f(xs: list[int]) -> int:
    i = 0
    total = 0
    while xs[i] >= 0:
        try:
            total += xs[i]
            i += 1
        except IndexError:
            return -2
    return total

def main() -> int:
    print(f([4, 5, -1]))
    print(f([4, 5, 6]))
    return 0

main()
'''
        self.assertFalse(tryhoist.rewrite(pythons(source)))
        reference = self.oracle('header_raises', source)
        self.assertEqual(reference[0], 1)
        for rewrite in (False, True):
            self.assertEqual(self.run_exe(self.build('header_raises', source, rewrite))[0], 1)


if __name__ == '__main__':
    unittest.main()
