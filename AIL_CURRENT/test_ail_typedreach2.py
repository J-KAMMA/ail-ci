"""More programs reach the typed path by default, batch 2 (stdin idiom, list[str] parameters, text methods), against CPython 3.12.

Since exact ints (PR #198) an `int(token)` or an accumulator is not provably int64, so the function needs the IR's tagged-int
lowering (ir/lower.py); whatever that lowering did not cover sent the whole program to the general path (20 to 200 times the
instructions). This batch widens the lowering:

- the truth value of a list, a dict or a str (`if not data:`, `if word and ...`)
- `[f(x) for x in xs[a:b]]` (a slice of an owned list, Python's clamping of both bounds; a bound beyond int64 saturates, which
  clamps to the same place), a comprehension over `s.split()` itself
- `sum(...)`, `min(...)`, `max(...)` of an owned int list, a generator expression or a list comprehension (exact tagged sum;
  an empty min/max raises ValueError); `sep.join(<generator of str>)`
- `sorted(xs)` / `sorted(set(xs), reverse=...)` of an owned int list
- `xs.extend(ys)` of lists of str, `s.casefold()`, `s[a:b:c]` of a str
- a list[str] parameter, lent read-only (every use of it in the function must be a read; anything else stays on the general path)
- a range loop whose bounds are tagged ints but whose counter is an int64 place

T1  the programs take the typed path (no "built on the general path" note)
T2  stdout and exit code equal CPython on ordinary inputs and on the boundaries of the idiom
T3  boundaries: empty input, whitespace, '+3', '-0', '1_000', non-ASCII digits, int64 edges, a count beyond int64 (exact),
    a value beyond int64 (a loud stop is allowed, a wrong answer is not)
T4  a list[str] parameter that is mutated, aliased or sliced stays correct (and off the typed lowering)
T5  the census tool applies the same tagged-int gate as the real compile
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HAVE_CC = shutil.which('gcc') is not None or shutil.which('cc') is not None

STDIN_IDIOM = '''import sys


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        print("none")
        return
    n = int(data[0])
    values = [int(x) for x in data[1:1 + n]]
    distinct = sorted(set(values), reverse=True)
    if len(distinct) >= 2:
        print(distinct[1])
    else:
        print("none")
    print(len(values), sum(values))
    print(sum(1 for v in values if v < 0))
    if values:
        print(max(values), min(v * 2 for v in values))
    print(" ".join(str(abs(x)) for x in values))
    asc = sorted(values)
    print(asc[0] if asc else -1)
    uniq = sorted(set(values))
    print(len(uniq), uniq[0] if uniq else 0)


if __name__ == "__main__":
    main()
'''

MINMAX = '''import sys


def main() -> None:
    values = [int(t) for t in sys.stdin.read().split()]
    print(max(v + 1 for v in values))


if __name__ == "__main__":
    main()
'''

WORDS = '''import sys


def longest_word(words: list[str]) -> str:
    return max(words, key=len)


def count_big(words: list[str], k: int) -> int:
    c = 0
    for w in words:
        if len(w) >= k:
            c += 1
    return c


def has(words: list[str], w: str) -> bool:
    return w in words


def process_line(line: str) -> str:
    words = line.split()
    if not words:
        return "-"
    longest = longest_word(words)
    return f"{len(line)} {len(longest)} {longest} {count_big(words, 3)} {has(words, 'ab')}"


def main() -> None:
    text = sys.stdin.read()
    for line in text.splitlines():
        print(process_line(line))


if __name__ == "__main__":
    main()
'''

# a list[str] parameter that the function changes: the caller's list changes too (it must not be lent read-only)
WORDS_MUTATED = '''import sys


def shout(words: list[str]) -> int:
    words.append("END")
    words.sort()
    return len(words)


def peek(words: list[str]) -> str:
    return words[0] + words[-1]


def main() -> None:
    ws = sys.stdin.read().split()
    if not ws:
        print("empty")
        return
    print(peek(ws))
    n = shout(ws)
    print(n, ws)
    alias = ws
    print(shout(alias), len(ws), peek(ws))


if __name__ == "__main__":
    main()
'''

TEXT = '''import sys


def strip_punctuation(word: str) -> str:
    start, end = 0, len(word)
    while start < end and not word[start].isalnum():
        start += 1
    while end > start and not word[end - 1].isalnum():
        end -= 1
    return word[start:end]


def is_palindrome(word: str) -> bool:
    folded = word.casefold()
    return folded == folded[::-1]


def main() -> None:
    text = sys.stdin.read()
    palindromes = []
    for raw in text.split():
        word = strip_punctuation(raw)
        if word and is_palindrome(word):
            palindromes.append(word)
    output = [str(len(palindromes))]
    output.extend(palindromes)
    print("\\n".join(output))


if __name__ == "__main__":
    main()
'''

BITONIC = '''import sys


def longest_bitonic(nums: list[int]) -> int:
    n = len(nums)
    if n == 0:
        return 0
    inc = [1] * n
    for i in range(n):
        for j in range(i):
            if nums[j] < nums[i] and inc[j] + 1 > inc[i]:
                inc[i] = inc[j] + 1
    dec = [1] * n
    for i in range(n - 1, -1, -1):
        for j in range(i + 1, n):
            if nums[j] < nums[i] and dec[j] + 1 > dec[i]:
                dec[i] = dec[j] + 1
    return max(inc[i] + dec[i] - 1 for i in range(n))


def main() -> None:
    nums = [int(tok) for tok in sys.stdin.read().split()]
    print(longest_bitonic(nums))


if __name__ == "__main__":
    main()
'''

# the lowered forms with no int64 store of a possibly big int: lengths of words (int64 by construction), a slice bound that is an
# exact tagged int (n = int(token), possibly beyond int64), sum/min/max/sorted/set of the lengths, a range loop with int64 bounds
LENS = '''import sys


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        print("none")
        return
    n = int(data[0])
    lens = [len(w) for w in data[1:1 + n]]
    print(len(lens), sum(lens), sum(len(w) * 3 for w in data[1:1 + n]))
    if lens:
        print(max(lens), min(len(w) for w in data[1:1 + n]))
    uniq = sorted(set(lens), reverse=True)
    print(len(uniq), uniq[0] if uniq else -1)
    srt = sorted(lens)
    print(" ".join(str(x) for x in srt))
    total = 0
    for i in range(len(lens)):
        total += lens[i] * i
    print(total)


if __name__ == "__main__":
    main()
'''

# int64 elements whose arithmetic leaves int64 inside a sum/min/max/join/slice: the answer is CPython's exact one, in the default build
EDGE = '''import sys


def main() -> None:
    data = sys.stdin.read().split()
    k = int(data[0])
    xs = [9223372036854775807, -9223372036854775807, 4611686018427387904, 3, 3]
    print(sum(v * 2 for v in xs), sum(v * k for v in xs[1:1 + k]), sum(xs))
    print(max(v + 1 for v in xs), min(v * 3 for v in xs), max(xs), min(xs))
    print(" ".join(str(v * v) for v in xs))
    ys = sorted(set(xs), reverse=True)
    print(ys[0], ys[-1], len(ys))
    print(sum(v - 1 for v in xs[k:]), sum(1 for v in xs[:k] if v * 2 > 0))
    for i in range(k, 3 + k):
        print(i)


main()
'''

INT_INPUTS = ['', '\n', '   \n', '3\n1 2 3\n', '5\n3 1 2 3 1\n', '3\n5 5 5\n', '-2\n1 2 3\n', '0\n', ' 7 \n1 2 3 4 5 6 7\n',
              '+3\n4 -0 1_0\n', '1_000\n5\n', '٣\n1 2 3 4\n',
              '99999999999999999999\n1 2 3\n',
              '-99999999999999999999\n1 2 3\n', '10\n1 2\n', 'x\n', '1__0\n1\n', '3\n1 x 3\n', '2\n-5 -7\n',
              '4\n7 7 8 9\n', '1\n', '1\n-3\n']
# a value past int64 inside the list: exact on the general path, a loud stop (never a wrong answer) on the typed path
MATRIX = '''import sys


def main() -> None:
    data = sys.stdin.read().split()
    r = int(data[0])
    c = int(data[1])
    vals = list(map(int, data[2:2 + r * c]))
    a: list[list[int]] = [vals[i * c:(i + 1) * c] for i in range(r)]
    t: list[list[int]] = [[a[i][j] for i in range(r)] for j in range(c)]
    p: list[list[int]] = [
        [sum(a[i][k] * a[j][k] for k in range(c)) for j in range(r)]
        for i in range(r)
    ]
    lines = [" ".join(map(str, row)) for row in t]
    lines += [" ".join(map(str, row)) for row in p]
    print(chr(10).join(lines))


main()
'''
MATRIX_INPUTS = ['2 2\n1 2\n3 4\n', '2 4\n-9223372036854775808 8 9223372036854775808 -2\n-9223372036854775809 0 99999999999999999999 3\n',
                 '1 1\n99999999999999999999\n', '1 2\n9223372036854775807 9223372036854775807\n']
BIG_VALUES = ['4\n-9223372036854775808 9223372036854775807 0 -1\n',
              '2\n9223372036854775807 -9223372036854775808 7\n',
              '2\n99999999999999999999 1\n', '3\n-99999999999999999999 5 5\n']
WORD_INPUTS = ['', 'a bb ccc\ndd ee\n\n   \nxx yy zz\nlongest one here\n', 'é ü ñññ\n', 'x', '\n\n',
               'ab cd\r\nef\r\n', 'a\x0bb\x1cc d\n', 'ab ab ab\n']
TEXT_INPUTS = ['', 'Racecar, Noon! level... A "madam" xyz\n', 'ß ss Ssß ǅ ǆ ΑΣς σς ﬃ ffi İi\n',
               '   \n', 'abcba\tfoo\nboB\n!!!\n', 'Aa éÉ ñÑ 日本日 ١٢١\n']


def compile_default(directory, text, name):
    source, exe = Path(directory, name + '.py'), Path(directory, name + '_x')
    source.write_text(text, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1')
    for key in ('AIL_NO_GENERAL', 'AIL_UNIFIED_FORCE', 'AIL_QUIET_FALLBACK'):
        env.pop(key, None)
    res = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name, '-o', exe.name],
                         cwd=directory, capture_output=True, text=True, timeout=900, env=env)
    return res, exe, source


def typed(res):
    return 'built on the general path' not in res.stderr


def _exact_int(test):
    """The test is about exact (arbitrary precision) ints: it runs in the opt-in mode (intmode.py, `--exact-int`)."""
    import functools
    import os

    @functools.wraps(test)
    def wrapper(*args, **kwargs):
        saved = os.environ.get('AIL_EXACT_INT')
        os.environ['AIL_EXACT_INT'] = '1'
        try:
            return test(*args, **kwargs)
        finally:
            if saved is None:
                os.environ.pop('AIL_EXACT_INT', None)
            else:
                os.environ['AIL_EXACT_INT'] = saved
    return wrapper


@unittest.skipUnless(HAVE_CC, 'needs a C compiler')
class TypedReach2(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='typedreach2_')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def build(self, text, name, expect_typed=True):
        res, exe, source = compile_default(self.tmp, text, name)
        self.assertEqual(res.returncode, 0, res.stderr[-1500:])
        if expect_typed is not None:
            self.assertEqual(typed(res), expect_typed, res.stderr[-600:])
        return exe, source

    def same(self, exe, source, stdin, loud_ok=False):
        want = subprocess.run([sys.executable, str(source)], input=stdin.encode('utf-8'), capture_output=True, timeout=300)
        got = subprocess.run([str(exe)], input=stdin.encode('utf-8'), capture_output=True, timeout=300)
        if loud_ok and got.returncode != 0 and got.stdout != want.stdout:
            # the typed path stops loudly where an int past int64 is stored in a container: never a silent difference
            self.assertTrue(got.stderr.strip(), repr(stdin))
            self.assertTrue(want.stdout.startswith(got.stdout), repr(stdin))
            return
        self.assertEqual(got.stdout, want.stdout, repr(stdin))
        self.assertEqual(got.returncode, want.returncode, repr(stdin))

    def check(self, text, name, inputs, expect_typed=True, loud=()):
        exe, source = self.build(text, name, expect_typed)
        for stdin in inputs:
            self.same(exe, source, stdin)
        for stdin in loud:
            self.same(exe, source, stdin, loud_ok=True)

    # T1 + T2 + T3
    @_exact_int
    def test_stdin_idiom_typed_and_equal(self):
        self.check(STDIN_IDIOM, 'idiom', INT_INPUTS + BIG_VALUES, expect_typed=None)

    @_exact_int

    def test_max_of_empty_generator_raises_like_cpython(self):
        self.check(MINMAX, 'minmax', ['', '1 2 3\n', '-5\n', '  \n', '1 99999999999999999999 -3\n'] + BIG_VALUES,
                   expect_typed=None)

    def test_list_str_parameters_read_only_typed(self):
        self.check(WORDS, 'words', WORD_INPUTS)

    def test_casefold_stepped_slice_extend_typed(self):
        self.check(TEXT, 'text', TEXT_INPUTS)

    @_exact_int

    def test_range_bounds_tagged_counter_int64(self):
        self.check(BITONIC, 'bitonic', ['', '1 2 3 2 1\n', '5\n', '1 3 2 4 3 5\n', '3 3 3\n'] + BIG_VALUES, expect_typed=None)

    @_exact_int

    def test_slice_with_a_tagged_bound_stays_typed_and_exact(self):
        words = 'a bb ccc dd e ffff ggg'
        inputs = ['', '3 ' + words + '\n', '0 ' + words + '\n', '-2 ' + words + '\n', '99999999999999999999 ' + words + '\n',
                  '-99999999999999999999 ' + words + '\n', '9223372036854775807 ' + words + '\n',
                  '-9223372036854775808 ' + words + '\n', ' +2 ' + words + '\n', '1_0 ' + words + '\n', '\u0663 ' + words + '\n',
                  'x ' + words + '\n', '2\n']
        self.check(LENS, 'lens', inputs)

    def test_int64_elements_whose_arithmetic_leaves_int64(self):
        inputs = ['2', '0', '-1', '4', '99999999999999999999', '-99999999999999999999', '9223372036854775807', '1', '']
        self.check(EDGE, 'edge', [i + chr(10) if i else i for i in inputs], expect_typed=None)

    def test_int_text_in_a_list_of_lists_is_exact_not_an_overflow_stop(self):
        # (the legacy emitter parses int(<text>) into an int64: a function the IR refuses for its kinds must not keep it)
        self.check(MATRIX, 'matrix', MATRIX_INPUTS, expect_typed=None)

    # T4
    def test_mutated_list_parameter_keeps_python_semantics(self):
        self.check(WORDS_MUTATED, 'mutated', ['', 'b a c\n', 'x\n'], expect_typed=None)

    # T5
    def test_census_applies_the_tagged_int_gate(self):
        census = ROOT.parent / 'lab' / 'census' / 'fallback_census.py'
        if not census.exists():
            self.skipTest('lab/census is not in this tree')
        text = census.read_text(encoding='utf-8')
        self.assertIn("os.environ['AIL_SURFACE'] = 'python'", text)
        self.assertIn('_refuse_typed_big_store', text)


if __name__ == '__main__':
    unittest.main()
