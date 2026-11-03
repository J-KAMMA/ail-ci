"""Locals written inside a `try` body and read after the landing keep their value; locals no try
region mentions are no longer `volatile` / heap frame cells (C11 7.13.2.1p3: only an automatic
modified between setjmp and longjmp and read afterwards is indeterminate)."""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT / 'python/pkg-v12')]
from ail_syntax import translate as _ail_translate, detect as _ail_brace
def translate(source, **options):
    return _ail_translate(source, **options) if _ail_brace(source) else source
from test_ail_callable_values import oracle_source

CASES = {
    'handler_reads_scalar': """import sys

def bad(n: int) -> int:
    return 10 // n

def main() -> int:
    x = 1
    f = 0.5
    k = 0
    try:
        x = 5
        f = f + 2.25
        bad(0)
        x = 99
    except ZeroDivisionError:
        print(x, f)
    for i in range(3):
        k += i
    print(k, x)
    return 0

if __name__ == "__main__":
    sys.exit(main())
""",
    'loop_accumulates_across_raises': """import sys

def pick(i: int) -> int:
    if i % 3 == 0:
        raise ValueError
    return i * 2

def main() -> int:
    total = 0
    bad = 0
    last = -1
    for i in range(10):
        try:
            total += pick(i)
            last = i
        except ValueError:
            bad += 1
            print(total, last)
    print(total, bad, last)
    return 0

if __name__ == "__main__":
    sys.exit(main())
""",
    'read_before_write_each_iteration': """import sys

def boom(i: int) -> int:
    if i % 2 == 1:
        raise KeyError
    return i

def main() -> int:
    t = 0
    for i in range(6):
        try:
            t = t + 1
            t = t * 2
            boom(i)
            t = t + 100
        except KeyError:
            t = t - 1
    print(t)
    return 0

if __name__ == "__main__":
    sys.exit(main())
""",
    'nested_try_outer_handler': """import sys

def bad(n: int) -> int:
    return 7 // n

def main() -> int:
    a = 0
    b = 0
    c = 0
    try:
        a = 1
        try:
            b = 2
            bad(0)
            b = 3
        except KeyError:
            c = 50
        a = 4
    except ZeroDivisionError:
        print(a, b, c)
    c = c + 1
    print(a, b, c)
    return 0

if __name__ == "__main__":
    sys.exit(main())
""",
    'nested_try_inner_handler_then_outer': """import sys

def bad(n: int) -> int:
    return 7 // n

def main() -> int:
    a = 0
    b = 0
    try:
        try:
            a = 1
            bad(0)
        except ZeroDivisionError:
            a = a + 10
            b = a
            raise ValueError
        a = 1000
    except ValueError:
        print(a, b)
    print(a, b)
    return 0

if __name__ == "__main__":
    sys.exit(main())
""",
    'finally_reads_and_after': """import sys

def bad(n: int) -> int:
    return 7 // n

def work(flag: int) -> int:
    s = 0
    e = 0
    try:
        s = 3
        if flag > 0:
            bad(0)
        s = 4
    except ZeroDivisionError:
        e = s * 10
    finally:
        s = s + 1
        print(s, e)
    return s + e

def main() -> int:
    print(work(0))
    print(work(1))
    u = 0
    try:
        try:
            u = 8
            bad(0)
        finally:
            u = u + 1
            print(u)
    except ZeroDivisionError:
        print(u)
    print(u)
    return 0

if __name__ == "__main__":
    sys.exit(main())
""",
    'else_branch': """import sys

def bad(n: int) -> int:
    return 7 // n

def main() -> int:
    x = 0
    y = 0
    for i in range(2):
        try:
            x = x + 1
            bad(i)
            y = y + 1
        except ZeroDivisionError:
            y = y + 10
        else:
            y = y + 100
    print(x, y)
    return 0

if __name__ == "__main__":
    sys.exit(main())
""",
    'raise_from_callee_with_container_and_str': """import sys

def deep(n: int) -> int:
    if n > 2:
        raise ValueError
    return n

def main() -> int:
    items: list[int] = []
    untouched: list[int] = [1, 2, 3]
    s = 'a'
    m: dict[str, int] = {}
    n = 0
    try:
        for i in range(10):
            n = i
            s += 'b'
            m['k'] = i
            items.append(i)
            deep(i)
    except ValueError:
        print(n, s, len(items), len(m))
    untouched.append(4)
    print(len(untouched), len(items), s, m['k'])
    return 0

if __name__ == "__main__":
    sys.exit(main())
""",
    'body_private_scalars': """import sys

def main() -> int:
    after = 0
    try:
        y = 5
        y = y + 1
        z = y * 2.5
        print(y, z)
        raise ValueError
    except ValueError:
        after = 7
    print(after)
    return 0

if __name__ == "__main__":
    sys.exit(main())
""",
    'return_inside_try_and_handler_state': """import sys

def find(limit: int) -> int:
    seen = 0
    r = -1
    try:
        for i in range(limit):
            seen = seen + 1
            if i == 4:
                return seen
            if i == 7:
                raise IndexError
    except IndexError:
        r = seen
    return r

def main() -> int:
    print(find(3), find(5), find(9))
    return 0

if __name__ == "__main__":
    sys.exit(main())
""",
}

# main's locals: `x` is written in the try body and read in the handler (must stay volatile);
# `hot` and `idx` are mentioned by no try region (must not be).
C_CHECK = """import sys

def bad(n: int) -> int:
    return 10 // n

def main() -> int:
    x = 1
    hot = 0
    note = 'q'
    big: list[int] = []
    kept: list[int] = [1]
    for idx in range(5):
        hot += idx
        big.append(hot)
    try:
        x = 5
        kept.append(x)
        bad(0)
    except ZeroDivisionError:
        print(x)
    print(hot, len(big), len(kept), note)
    return 0

if __name__ == "__main__":
    sys.exit(main())
"""


def oracle(source):
    program = oracle_source(translate(source))
    result = subprocess.run([sys.executable, '-X', 'utf8', '-c', program], capture_output=True, timeout=60,
                            env=dict(os.environ, PYTHONUTF8='1'))
    return result.returncode, result.stdout.replace(b'\r\n', b'\n'), result.stderr


@unittest.skipUnless(os.environ.get('PIPE_CC') or shutil.which('cc') or shutil.which('gcc'),
                     'installed C compiler required')
class TryLocalsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='ail-try-locals-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()

    def build(self, name, source, debug=False):
        path = self.root / (name + '.ail')
        path.write_text(source, encoding='utf8')
        output = self.root / name
        args = [sys.executable, '-X', 'utf8', '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', str(path), '-o', str(output)]
        if debug:
            args += ['--debug-dir', str(self.root / (name + '-debug'))]
        result = subprocess.run(args, capture_output=True, timeout=180, env=dict(os.environ, PYTHONUTF8='1'))
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        return output if output.is_file() else Path(str(output) + '.exe')

    def test_matches_cpython(self):
        for name, source in CASES.items():
            with self.subTest(name):
                expected = oracle(source)
                self.assertEqual(expected[0], 0, expected[2].decode(errors='replace'))
                exe = self.build(name, source)
                result = subprocess.run([str(exe)], capture_output=True, timeout=30)
                self.assertEqual((result.returncode, result.stdout.replace(b'\r\n', b'\n'), result.stderr),
                                 (expected[0], expected[1], b''))

    def main_declarations(self, source, name):
        # (the declarations the legacy emitter writes are inspected here, whatever AIL_IR says)
        saved = os.environ.get('AIL_IR')
        os.environ['AIL_IR'] = '0'
        try:
            self.build(name, source, debug=True)
        finally:
            if saved is None:
                os.environ.pop('AIL_IR', None)
            else:
                os.environ['AIL_IR'] = saved
        text = (self.root / (name + '-debug') / 'program.c').read_text(encoding='utf8')
        start = text.index('int64_t py_main(void) {')
        return text[start:text.index('\n}\n', start)]

    def test_untouched_locals_are_plain_and_written_ones_stay_qualified(self):
        body = self.main_declarations(C_CHECK, 'ccheck')
        self.assertRegex(body, r'\n    volatile int64_t v_x = 0;')
        self.assertRegex(body, r'\n    int64_t v_hot = 0;')
        self.assertRegex(body, r'\n    int64_t v_idx = 0;')
        self.assertNotRegex(body, r'volatile int64_t v_(hot|idx)\b')
        # a str / list no try region mentions is an ordinary automatic, not a heap cell
        self.assertRegex(body, r'\n    ail_str v_note = \{0\};')
        self.assertRegex(body, r'\n    ail_list v_big = \{0\};')
        self.assertNotIn('v_big = &', body)
        # the list appended inside the try keeps its cell, through a pointer that is not volatile
        self.assertRegex(body, r'\n    ail_list \* const v_kept = &_ail_frame_cells->v_kept;')
        self.assertNotRegex(body, r'\* volatile v_(kept|big|note)\b')
        self.assertNotIn('/*@AIL', body)

    def test_no_markers_leak_into_generated_c(self):
        for name, source in CASES.items():
            with self.subTest(name):
                self.build(name, source, debug=True)
                text = (self.root / (name + '-debug') / 'program.c').read_text(encoding='utf8')
                self.assertNotIn('@AILTRY', text)
                self.assertNotIn('@AILEND', text)


if __name__ == '__main__':
    unittest.main()
