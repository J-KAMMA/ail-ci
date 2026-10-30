"""More run-time error texts and silent differences of the general path, against CPython 3.12.

Follows test_ail_cmp_classname (PR #248).  Every statement runs inside ``try/except Exception`` and prints
``type(e).__name__, e``; the expected output is CPython's own.  Built the default way and with
AIL_UNIFIED_FORCE=1.  A text that holds an object address (``<__main__.P object at 0x7f...>``) is compared with
the hex digits blanked, since CPython's address differs from run to run.

Fixed here:
1. ``sorted`` / ``list.sort`` ask ``later < earlier`` in the order CPython's timsort asks (count_run, binary insertion,
   merge_collapse), so an unorderable pair names its types in CPython's order (``sorted([1, "a"])`` says ``'str' and
   'int'``).  min()/max() already did.
2. ``x += y`` and the other augmented operators say ``+=`` in ``unsupported operand type(s) for +=: ...``; ``//``, ``%``,
   ``/`` and ``**`` named no types at all.  ``d |= other`` / ``d | other`` on a dict that is not known to be one at
   compile time raised a TypeError.
3. Wording: ``[*p]``, ``(*p,)``, ``''.join(p)`` / ``b''.join(p)``, ``math.sqrt(p)`` and the other
   ``math`` functions, ``open(p)``, ``str(p, 'utf8')``, ``bytearray(p)``, 3-argument ``pow``.
4. ``print(sep=p)`` / ``end=p`` raise ``TypeError: sep must be None or a string, not P`` (the output used to differ,
   or the program crashed); ``sep=None`` / ``end=None`` mean the default.
5. ``raise p`` / ``raise P()`` / ``raise P`` with a class that is no exception raise ``TypeError: exceptions must
   derive from BaseException`` (a catchable one).
6. An instance with no ``__repr__`` shows ``<__main__.P object at 0x...>``, so a missing-key KeyError, ``print(p)`` and
   ``repr(p)`` match CPython but for the address.

Left: ``print(*p)`` of a non-iterable (the call is lowered to a for loop before the general path sees it),
``math.floor`` / ``math.ceil`` / ``math.trunc`` of a value that is no number (the typed and the general path share
the lowering ``int(x // 1)``), and the first failing pair of ``heapq.nlargest`` / ``nsmallest`` with mixed types.
"""
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

PRELUDE = '''
import math
import heapq
import bisect


class P:
    pass


class Q(P):
    pass


class R:
    def __repr__(self):
        return "R!"


class S:
    def __str__(self):
        return "S-str"


class E(Exception):
    pass


def main():
    p = P()
    q = Q()
    r = R()
    s = S()
'''

SORT = [
    'sorted([1, "a"])',
    'sorted(["a", 1])',
    'sorted([1, 2, "a"])',
    'sorted([3, 2, "a", 1])',
    'sorted([3, 2, 1, "a"])',
    'sorted(["a", "b", 1, 2])',
    'sorted([1, 2.5, "a"])',
    'sorted(["a", 1.5, 2])',
    'sorted([p, 1])',
    'sorted([1, p])',
    'sorted([p, p])',
    'sorted([p, q])',
    'sorted([p, "a"])',
    'sorted([None, 1])',
    'sorted([1, None, 2])',
    'sorted([(1,), 1])',
    'sorted([[1], (1,)])',
    'sorted([{1}, 1])',
    'sorted([[1, 2], [1, "a"], [0, 1]])',
    'sorted([(1, 2), (1, "a"), (0, 1)])',
    'sorted([3, 1, 2, "a"], reverse=True)',
    'sorted([1, "a"], key=lambda v: v)',
    'sorted([True, "a"])',
    'sorted({1: 1, "a": 2})',
    'sorted(list(range(100)) + ["a"])',
    'sorted(["a"] + list(range(100)))',
    'sorted(list(range(70, 0, -1)) + list(range(10)) + ["x"] + list(range(5)))',
    'sorted([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, "a"])',
    'xs = [1, "a"]; xs.sort()',
    'xs = ["a", 1.5, 2]; xs.sort()',
    'xs = [2, "a", 1]; xs.sort(reverse=True)',
    'min(1, "a")',
    'min("a", 1)',
    'max(1, "a")',
    'max("a", 1)',
    'min([1, "a"])',
    'max([1, "a", 2])',
    'min(["a", 1, 2])',
    'min(1, p)',
    'max(p, 1)',
    'hp = []; heapq.heappush(hp, 1); heapq.heappush(hp, "a")',
    'hp = []; heapq.heappush(hp, "a"); heapq.heappush(hp, 1)',
    'heapq.heapify([1, "a", 2])',
    'heapq.heapify(["a", 1, 2])',
    'bisect.bisect_left([1, 2], "a")',
    'bisect.bisect_right([1, 2], "a")',
    'bisect.bisect_left(["a", "b"], 1)',
    'bisect.insort([1, 2], "a")',
]

AUG = [
    'x = 1; x += "a"',
    'x = p; x += p',
    'x = p; x -= 1',
    'x = 1; x *= p',
    'x = [1]; x += 5',
    'x = "s"; x += 5',
    'x = 2; x **= 2; x **= "a"',
    'x = 2; x //= "a"',
    'x = 2; x %= None',
    'x = 2; x <<= 1.5',
    'x = 2; x >>= "a"',
    'x = 2; x &= 1.5',
    'x = 2; x |= "a"',
    'x = 2; x ^= [1]',
    'x = 2.5; x /= "a"',
    'x = 2.5; x /= None',
    'x = [1]; x *= "a"',
    'x = (1,); x += [1]',
    'x = {1}; x |= [1]',
    'x = {1}; x -= [1]',
    'x = {1}; x &= 3',
    'x = {1}; x ^= 3',
    'l = [1, 2]; l[0] += "a"',
    'd = {"a": 1}; d["a"] += "x"',
    'p.v = 1; p.v += "x"',
    'x = None; x += 1',
    'x = 1; x += None',
    'x = "a"; x *= "b"',
    'x = 5; x += p',
    'x = [1]; x += p',
    'x = 5; x /= 0',
    # the plain operators name their operand types too (// % / ** used to name none)
    '1 // "a"',
    '1 % None',
    '1 / "a"',
    '2 ** "a"',
    '"a" // 2',
    '[1] / 2',
    '(1,) % 2',
    'None ** 2',
    '2.5 // "a"',
    'p // 1',
    '1 // p',
    '2 ** p',
    'q % 3',
    # dict |= / | on a value the compiler does not know to be a dict
    'd = {1: 2}; e = d; d |= {3: 4}; print(e, d)',
    'd = {1: 2}; d |= [(5, 6)]; print(d)',
    'd = {1: 2}; d |= 5',
    'd = {1: 2}; d |= [1]',
    'd = {1: 2}; d |= "ab"',
    'd = {1: 2}; d |= [(1, 2, 3)]',
    'd = {1: 2}; y = d | 5',
    'd = {1: 2}; y = d | [(1, 2)]',
    'd = {1: 2}; y = d | {3: 4}; print(d, y)',
]

WORDING = [
    '[*p]',
    '[*5]',
    '[*None]',
    '[1, *p, 2]',
    '(*p,)',
    '(*5,)',
    "''.join(p)",
    "''.join(5)",
    "''.join(None)",
    "''.join(r)",
    "','.join(p)",
    "''.join([1])",
    "''.join(['a', p])",
    "b','.join(p)",
    "b','.join(5)",
    "math.sqrt(p)",
    "math.sqrt('a')",
    "math.sqrt(None)",
    "math.sqrt(-1)",
    "math.sin(p)",
    "math.cos('a')",
    "math.exp(p)",
    "math.log(p)",
    "math.log(2, p)",
    "math.fabs(p)",
    "math.atan2(p, 1)",
    "math.atan2(1, 'a')",
    "math.hypot(p, 1)",
    "math.copysign(p, 1)",
    "math.pow(p, 2)",
    "math.fmod(1, p)",
    "math.isnan(p)",
    "math.isinf('a')",
    "math.isfinite(None)",
    "math.degrees(p)",
    "math.radians('a')",
    "math.isqrt(p)",
    "math.isqrt(1.5)",
    "math.gcd(p, 2)",
    "math.gcd(2, 1.5)",
    "math.factorial(p)",
    "math.factorial(2.5)",
    "math.sqrt(True) + math.sin(1) + math.hypot(3, 4)",
    "open(p)",
    "open(None)",
    "open(1.5)",
    "str(p, 'utf8')",
    "str(1, 'utf8')",
    "str(b'a', p)",
    "str(b'a', 'utf8', p)",
    "str('a', 'utf8')",
    "str(None, 'utf8')",
    "bytearray(p)",
    "bytearray(1.5)",
    "bytearray('a')",
    "bytearray('a', p)",
    "bytearray(-1)",
    "bytes(p)",
    "bytes(1.5)",
    "bytes('a')",
    "bytes('a', p)",
    "bytes([p])",
    "bytes([300])",
    "pow(p, 2, 5)",
    "pow(2, p, 5)",
    "pow(2, 3, p)",
    "pow('a', 2, 5)",
    "pow(2, 'a', 5)",
    "pow(2, 3, None)",
    "pow(2, -1, 0)",
    "pow(2.5, 2, 5)",
    "pow(2, 2.5, 5)",
    "pow(2, 2, 5.0)",
    "pow(p, 2)",
    "pow(2, p)",
    "sum([1], 'a')",
    "sum([1], b'a')",
    "sum([1], bytearray(b'a'))",
    "sum([1, 2], 10)",
    "sum(5, 'a')",
]

PRINT = [
    'print("a", sep=p)',
    'print("a", end=p)',
    'print("a", sep=1)',
    'print("a", end=1)',
    'print("a", sep=None)',
    'print("a", end=None)',
    'print("a", "b", sep=None, end=None)',
    'print("a", sep=b"x")',
    'print("a", end=1.5)',
    'print("a", sep=[1])',
    'print("a", "b", sep=p)',
    'print("a", sep="")',
    'print("a", end="")',
    'print(sep=p)',
    'print(end=p)',
    'print(p, sep=p)',
    'print("a", sep=p, end=3)',
    'print("a", sep=" ", end=3)',
    'print("a", "b", sep="-", end="!\\n")',
    'print(*[1, 2])',
]

RAISE = [
    'raise P()',
    'raise p',
    'raise P',
    'raise q',
    'raise 1',
    'raise "boom"',
    'raise None',
    'raise [1]',
    'raise (1, 2)',
    'raise 1.5',
    'raise E',
    'raise E("x")',
    'raise ValueError',
    'raise KeyError("k")',
    'raise ZeroDivisionError',
]

KEYS = [
    'd = {1: 2}; d[r]',
    '{}[s]',
    '{}[(1, r)]',
    '{"a": 1}["b"]',
    '{}[(1, "x")]',
    '{}.pop(r)',
    'set().remove(r)',
    '{}[None]',
    '{}[1.5]',
    '{}[b"x"]',
    '{}[True]',
    '{}["it\'s"]',
    '{}[2 ** 70]',
    '{}.pop("zz")',
    '{1}.remove(5)',
    '{}[(r, s)]',
    '{}[p].x',
    '{}[p]',
    '{}[q]',
]

REPRS = [
    'print(p)',
    'print(repr(p))',
    'print(str(p))',
    'print(f"{p}")',
    'print([p])',
    'print("%s" % p)',
    'print({1: p})',
    'print(q)',
    'print((p, 1))',
    'print(r, [r], s, [s])',
]


def tryblock(i, stmt):
    lines = ['    try:']
    for part in stmt.split('; '):
        lines.append('        ' + part)
    lines.append('        print(%d, "no error")' % i)
    lines.append('    except Exception as e:')
    lines.append('        print(%d, type(e).__name__, e)' % i)
    return lines


def wrap(prelude, stmts):
    out = [prelude.rstrip('\n')]
    for i, st in enumerate(stmts):
        out.extend(tryblock(i, st))
    out.append('')
    out.append('main()')
    return '\n'.join(out) + '\n'


CASES = {
    'sort_order': wrap(PRELUDE, SORT),
    'aug_ops': wrap(PRELUDE, AUG),
    'wording': wrap(PRELUDE, WORDING),
    'print_sep_end': wrap(PRELUDE, PRINT),
    'raise_non_exception': wrap(PRELUDE, RAISE),
    'keyerror_key_repr': wrap(PRELUDE, KEYS),
    'default_repr': wrap(PRELUDE, REPRS),
}

# a sort that works must keep working: the same values, the same stable order
CASES['sort_values'] = '''
def main():
    xs = [5, 3, 9, 1, 7, 2, 8, 2, 4, 6, 3, 3, 1, 0, 11, 15, 14, 13, 12]
    print(sorted(xs), sorted(xs, reverse=True), sorted(xs, key=lambda v: -v))
    ys = ["b", "a", "c", "B", "A", "cc", "aa"]
    ys.sort()
    print(ys)
    ys.sort(key=len, reverse=True)
    print(ys)
    big = [(i * 7919) % 1009 for i in range(500)]
    print(sorted(big)[:10], sorted(big, reverse=True)[:10], sum(sorted(big)[i] * i for i in range(500)))
    runs = list(range(100, 0, -1)) + list(range(50)) + list(range(200, 150, -1))
    print(sorted(runs)[:5], sorted(runs, key=lambda v: v % 10)[:12])
    st = sorted([(1, "b"), (1, "a"), (0, "z"), (1, "a")] * 20)
    print(st[:5], st[-3:])
    words = ["pear", "fig", "apple", "kiwi", "plum", "date", "lime", "nut"] * 9
    print(sorted(words, key=len)[:12], sorted(words, key=len, reverse=True)[:12])
    fl = [((i * 37) % 101) / 7.0 for i in range(150)]
    print(sorted(fl)[:6], sorted(fl)[-3:])
    mixed = [1, 2.5, True, 0, -3, 2, 1.0, 2.5]
    print(sorted(mixed), sorted(mixed, reverse=True))
    ms = [[3, 1], [2, 9], [3, 0], [2, 1], []] * 15
    print(sorted(ms)[:6])


main()
'''

UNCAUGHT = {
    'uncaught_print_sep': 'class P:\n    pass\n\nprint("a", sep=P())\n',
    'uncaught_print_end': 'class P:\n    pass\n\nprint("a", end=3)\n',
    'uncaught_raise_inst': 'class P:\n    pass\n\nraise P()\n',
    'uncaught_raise_int': 'raise 1\n',
    'uncaught_sort': 'print(sorted([1, "a"]))\n',
    'uncaught_aug': 'x = 1\nx += "a"\n',
}

HEX = re.compile(r'0x[0-9a-fA-F]+')


def blank(text):
    return HEX.sub('0xADDR', text)


def compile_source(directory, name, source, mode):
    path = Path(directory) / (name + '.py')
    path.write_text(source, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    for key in ('AIL_UNIFIED_FORCE', 'AIL_NO_GENERAL'):
        env.pop(key, None)
    if mode == 'force':
        env['AIL_UNIFIED_FORCE'] = '1'
    exe = Path(directory) / (name + '_' + mode)
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', path.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    return built, exe


def run_cpython(directory, name, source):
    path = Path(directory) / (name + '_cpython.py')
    path.write_text(source, encoding='utf-8')
    ran = subprocess.run([sys.executable, '-B', path.name], cwd=directory, capture_output=True,
                         text=True, timeout=120, encoding='utf-8')
    return ran.stdout.replace('\r\n', '\n'), ran.stderr.replace('\r\n', '\n'), ran.returncode


def last_line(text):
    lines = [line for line in text.splitlines() if line.strip()]
    return lines[-1] if lines else ''


class ErrText2(unittest.TestCase):
    def test_programs_print_what_cpython_prints(self):
        for slug, source in CASES.items():
            with tempfile.TemporaryDirectory(prefix='ail-errtext2-') as directory:
                expected, _, status = run_cpython(directory, slug, source)
            for mode in ('default', 'force'):
                with self.subTest(slug=slug, mode=mode), \
                        tempfile.TemporaryDirectory(prefix='ail-errtext2-') as directory:
                    built, exe = compile_source(directory, slug, source, mode)
                    self.assertEqual(built.returncode, 0, (slug, mode, built.stdout + built.stderr))
                    ran = subprocess.run([str(exe)], cwd=directory, capture_output=True, text=True,
                                         timeout=120, encoding='utf-8')
                    self.assertEqual(ran.returncode, status, ran.stdout + ran.stderr)
                    self.assertEqual(blank(ran.stdout.replace('\r\n', '\n')), blank(expected), ran.stderr)

    def test_uncaught_ends_the_way_cpython_does(self):
        for slug, source in UNCAUGHT.items():
            with tempfile.TemporaryDirectory(prefix='ail-errtext2-') as directory:
                expected, cpython_err, status = run_cpython(directory, slug, source)
            for mode in ('default', 'force'):
                with self.subTest(slug=slug, mode=mode), \
                        tempfile.TemporaryDirectory(prefix='ail-errtext2-') as directory:
                    built, exe = compile_source(directory, slug, source, mode)
                    self.assertEqual(built.returncode, 0, (slug, mode, built.stdout + built.stderr))
                    ran = subprocess.run([str(exe)], cwd=directory, capture_output=True, text=True,
                                         timeout=120, encoding='utf-8')
                    self.assertEqual(ran.returncode, status, ran.stdout + ran.stderr)
                    self.assertEqual(ran.stdout.replace('\r\n', '\n'), expected)
                    self.assertEqual(last_line(ran.stderr), last_line(cpython_err), ran.stderr)


if __name__ == '__main__':
    unittest.main()
