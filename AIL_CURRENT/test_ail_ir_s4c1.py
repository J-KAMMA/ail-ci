"""IR stage S4c-1: input windows (docs/design/IR_OWNERSHIP_DESIGN_v2.md section 16,
python/pkg-v12/ir/passes/window.py, the `IRWIN*` pieces of cruntime.py).

A whole-input read (`read_stdin_bytes`, `read_bytes`) that is scanned once, forward, becomes a read-only
mapping when the input is a regular file, and the scan gives the pages behind it back. What this module pins:

* the pass picks exactly the scans it can prove (a loop whose carried position bounds every index the loop
  touches), and leaves every other shape alone: a second pass over the data, an index below the position,
  a computed index, the buffer handed to a call, a read in a loop, a file whose loop calls a function;
* the IR build prints what the legacy build prints and what CPython prints (the builtins `read_stdin_bytes`,
  `read_bytes`, `write_stdout_bytes` are given to CPython as one-line prelude functions) -- for a regular-file
  stdin, a pipe, an empty input, an input below the mapping threshold, a read with a size limit followed by a
  second read, a stdin whose offset is not page aligned, a file that does not exist;
* the mapped path is exercised with tiny inputs (`AIL_IR_WINDOW_MIN=1`, `AIL_IR_WINDOW_STEP=4096`) and with a
  large one, where the peak RSS of the IR build is a fraction of the legacy build's -- and equal to it
  for a pipe, where the legacy read is kept;
* exceptions out of the scan (both modes), repeated calls (map, unmap) and ASan + UBSan + LSan: no report;
* with AIL_IR unset the generated C has none of the window runtime.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT / 'python' / 'pkg-v12'), str(ROOT)]

from ir import ir as I                       # noqa: E402
from ir import rtc, text, verify             # noqa: E402
from test_ail_ir_s3 import Built, compile_program, HAVE_CC     # noqa: E402
from ail_testenv import ASAN_DETECT_LEAKS

FORCE = {'AIL_IR_WINDOW_MIN': '1', 'AIL_IR_WINDOW_STEP': '4096'}

PRELUDE = '''import sys


def read_stdin_bytes(n):
    return sys.stdin.buffer.read() if n >= (1 << 30) else sys.stdin.buffer.read(n)


def read_bytes(path):
    return open(path, 'rb').read()


def write_stdout_bytes(b):
    sys.stdout.flush()
    sys.stdout.buffer.write(bytes(b))
    sys.stdout.buffer.flush()

'''


def cpython_run(directory, name, source, args=(), stdin_file=None, stdin=b''):
    path = Path(directory, name + '.py')
    path.write_text(PRELUDE + source)
    if stdin_file is not None:
        r = subprocess.run([sys.executable, str(path), *map(str, args)], stdin=stdin_file, capture_output=True,
                           timeout=300)
    else:
        r = subprocess.run([sys.executable, str(path), *map(str, args)], input=stdin, capture_output=True, timeout=300)
    return r.returncode, r.stdout, r.stderr


def run_exe(exe, args=(), stdin=b'', stdin_file=None, env=None):
    kw = dict(env=dict(os.environ, **(env or {})), capture_output=True, timeout=300)
    if stdin_file is not None:
        r = subprocess.run([str(exe), *map(str, args)], stdin=stdin_file, **kw)
    else:
        r = subprocess.run([str(exe), *map(str, args)], input=stdin, **kw)
    return r.returncode, r.stdout, r.stderr


# --------------------------------------------------------------------------------------------
# The programs (Python syntax; the builtins are the AIL ones, defined for CPython by PRELUDE)
# --------------------------------------------------------------------------------------------

LINES = '''
def main():
    data = read_stdin_bytes(1 << 40)
    n = len(data)
    i = 0
    lines = 0
    total = 0
    h = 0
    out = bytearray()
    while i < n:
        j = i
        while j < n and data[j] != 10:
            j += 1
        k = i
        while k < j:
            h = (h * 31 + data[k]) % 1000003
            k += 1
        if j - i > 3 and data[i] == 62:
            out.extend(data[i:j])
            out.append(10)
        total += j - i
        lines += 1
        i = j + 1
    print(lines, total, h)
    write_stdout_bytes(out)
    return 0


sys.exit(main())
'''

FOR_RANGE = '''
def main():
    data = read_stdin_bytes(1 << 40)
    n = len(data)
    t = 0
    c10 = 0
    for i in range(n):
        b = data[i]
        t = (t * 7 + b) % 99991
        if b == 10:
            c10 += 1
    print(n, t, c10)
    return 0


sys.exit(main())
'''

FIND = '''
def main():
    data = read_stdin_bytes(1 << 40)
    n = len(data)
    pos = 0
    count = 0
    acc = 0
    while pos < n:
        e = data.find(b"\\n", pos)
        if e < 0:
            e = n
        acc = (acc * 131 + (e - pos)) % 1000003
        if e - pos >= 2 and data[pos] == 65:
            count += 1
        pos = e + 1
    print(count, acc)
    return 0


sys.exit(main())
'''

TWO_PASS = '''
def main():
    data = read_stdin_bytes(1 << 40)
    n = len(data)
    lines = 0
    for i in range(n):
        if data[i] == 10:
            lines += 1
    t = 0
    for i in range(n):
        t = (t * 3 + data[i]) % 65521
    print(lines, t)
    return 0


sys.exit(main())
'''

BEHIND = '''
def main():
    data = read_stdin_bytes(1 << 40)
    n = len(data)
    i = 1
    t = 0
    while i < n:
        t = (t * 5 + data[i] + data[i - 1]) % 65521
        i += 1
    print(n, t)
    return 0


sys.exit(main())
'''

COMPUTED = '''
def main():
    data = read_stdin_bytes(1 << 40)
    n = len(data)
    t = 0
    i = 0
    while i < n:
        t = (t * 5 + data[(i * 7) % n]) % 65521
        i += 1
    print(n, t)
    return 0


sys.exit(main())
'''

PASSED = '''
def total(d: bytes) -> int:
    t = 0
    for x in d:
        t = (t + x) % 65521
    return t


def main():
    data = read_stdin_bytes(1 << 40)
    n = len(data)
    i = 0
    t = 0
    while i < n:
        t = (t + data[i]) % 65521
        i += 1
    print(n, t, total(data))
    return 0


sys.exit(main())
'''

LIMITED = '''
def main():
    head = read_stdin_bytes(1000)
    rest = read_stdin_bytes(1 << 40)
    t = 0
    for i in range(len(head)):
        t = (t * 3 + head[i]) % 65521
    u = 0
    j = 0
    while j < len(rest):
        u = (u * 5 + rest[j]) % 65521
        j += 1
    again = read_stdin_bytes(10)
    print(len(head), t, len(rest), u, len(again))
    return 0


sys.exit(main())
'''

TEXT_FIRST = '''
def main():
    line = input()
    data = read_stdin_bytes(1 << 40)
    t = 0
    for i in range(len(data)):
        t = (t + data[i]) % 65521
    print(len(line), t)
    return 0


sys.exit(main())
'''

FILE_SCAN = '''
def main():
    data = read_bytes(sys.argv[1])
    n = len(data)
    i = 0
    t = 0
    words = 0
    while i < n:
        if data[i] == 32 or data[i] == 10:
            words += 1
        t = (t * 17 + data[i]) % 99991
        i += 1
    print(n, words, t)
    return 0


sys.exit(main())
'''

FILE_CALL = '''
def mix(t: int, b: int) -> int:
    return (t * 17 + b) % 99991


def main():
    data = read_bytes(sys.argv[1])
    n = len(data)
    i = 0
    t = 0
    while i < n:
        t = mix(t, data[i])
        i += 1
    print(n, t)
    return 0


sys.exit(main())
'''

REPEAT = '''
def count(path: str) -> int:
    data = read_bytes(path)
    t = 0
    for i in range(len(data)):
        if data[i] == 10:
            t += 1
    return t


def main():
    s = 0
    for k in range(4):
        s += count(sys.argv[1]) * (k + 1)
    print(s)
    return 0


sys.exit(main())
'''

RAISING = '''
def scan(limit: int) -> int:
    data = read_stdin_bytes(1 << 40)
    n = len(data)
    i = 0
    t = 0
    while i < n:
        if data[i] == 33 and t > limit:
            raise ValueError("stop")
        t = (t + data[i]) % 65521
        i += 1
    return t


def main():
    try:
        print(scan(int(sys.argv[1])))
    except ValueError:
        print("caught")
    return 0


sys.exit(main())
'''

SLICES = '''
def main():
    data = read_stdin_bytes(1 << 40)
    n = len(data)
    i = 0
    out = bytearray()
    sums = 0
    while i < n:
        j = data.find(b"\\n", i)
        if j < 0:
            j = n
        line = data[i:j]
        sums = (sums + len(line)) % 65521
        if len(line) > 5:
            out.extend(line[2:5])
            out.append(10)
        i = j + 1
    print(sums)
    write_stdout_bytes(out)
    return 0


sys.exit(main())
'''

ALL = [('lines', LINES), ('for_range', FOR_RANGE), ('find', FIND), ('two_pass', TWO_PASS), ('behind', BEHIND),
       ('computed', COMPUTED), ('passed', PASSED), ('limited', LIMITED), ('slices', SLICES)]


def sample(size, seed=7):
    """Text-ish bytes with lines of every length, '>' headers, spaces and a final line without newline."""
    import random
    rng = random.Random(seed)
    out = bytearray()
    while len(out) < size:
        k = rng.choice((0, 1, 2, 5, 9, 40, 120))
        head = b'>' if rng.random() < 0.15 else b'A' if rng.random() < 0.2 else b''
        out += head + bytes(rng.choice(b'ACGT acgt\x80\xff!') for _ in range(k)) + b'\n'
    return bytes(out[:size])


def has_window(directory, name, tag='ir'):
    c = Path(directory, '%s.%s.d' % (name, tag), 'program.c').read_text()
    return ('ail_win_stdin(&' in c.split('int main(')[0] or 'ail_win_file(&' in c.split('int main(')[0]) \
        and 'ail_win_release(&' in c


class _Base(unittest.TestCase):
    maxDiff = None

    def build(self, tmp, name, source, env=None):
        tmp = tempfile.mkdtemp(dir=tmp)
        self.last_dir = tmp
        for tag, mode in (('legacy', {'AIL_IR': '0'}), ('ir', {'AIL_IR': 'verify'}),
                          ('ir-checked', {'AIL_IR': 'verify', 'AIL_IR_EXC': 'checked'})):
            built, _, _ = compile_program(tmp, name, 'import sys\n' + source, tag, dict(mode, **(env or {})), debug=True)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        return {t: Path(tmp, '%s.%s' % (name, t)) for t in ('legacy', 'ir', 'ir-checked')}


@unittest.skipUnless(HAVE_CC, 'no C compiler')
class PlanTests(_Base):
    def planned(self, name, source):
        with tempfile.TemporaryDirectory() as tmp:
            self.build(tmp, name, source)
            return has_window(self.last_dir, name)

    def test_forward_scans_are_windowed(self):
        for name, source in (('lines', LINES), ('for_range', FOR_RANGE), ('find', FIND), ('slices', SLICES),
                             ('limited', LIMITED)):
            with self.subTest(program=name):
                self.assertTrue(self.planned(name, source))

    def test_everything_else_is_left_alone(self):
        for name, source in (('two_pass', TWO_PASS), ('behind', BEHIND), ('computed', COMPUTED),
                             ('passed', PASSED)):
            with self.subTest(program=name):
                self.assertFalse(self.planned(name, source))

    def test_a_file_scan_is_windowed_unless_the_loop_calls_a_function(self):
        self.assertTrue(self.planned('file_scan', FILE_SCAN))
        self.assertFalse(self.planned('file_call', FILE_CALL))

    def test_the_text_read_before_a_binary_read_is_still_the_legacy_error(self):
        self.assertTrue(self.planned('text_first', TEXT_FIRST))

    def test_with_the_switch_off_the_generated_c_has_no_window_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            built, _, _ = compile_program(tmp, 'off', 'import sys\n' + LINES, 'off', {'AIL_IR': '0'}, debug=True)
            self.assertEqual(built.returncode, 0, built.stderr)
            c = Path(tmp, 'off.off.d', 'program.c').read_text()
        self.assertNotIn('ail_win', c)
        self.assertNotIn('IRWIN', c)

    def test_the_pass_can_be_switched_off_by_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            built, _, _ = compile_program(tmp, 'nopass', 'import sys\n' + LINES, 'ir', {'AIL_IR': 'verify',
                                          'AIL_IR_PASSES': 'mem2reg,simplify,ranges,licm'}, debug=True)
            self.assertEqual(built.returncode, 0, built.stderr)
            self.assertNotIn('ail_win', Path(tmp, 'nopass.ir.d', 'program.c').read_text())

    def test_new_runtime_entries_are_typed_and_have_effect_records(self):
        for name in ('read_stdin_win', 'read_bytes_win', 'win_release'):
            spec = rtc.ENTRIES[name]
            self.assertEqual(spec['attrs'], ('win',))
        self.assertEqual(rtc.ENTRIES['win_release']['results'], ())
        self.assertFalse(rtc.is_pure('win_release'))


@unittest.skipUnless(HAVE_CC, 'no C compiler')
class ProgramTests(_Base):
    def agree(self, tmp, name, source, args=(), data=b'', env=None, offset=0, expect_status=None, cpython=True):
        """Every build prints the same for a regular-file stdin and for a pipe, and CPython agrees."""
        exes = self.build(tmp, name, source)
        results = {}
        for tag, exe in exes.items():
            results[tag, 'pipe'] = run_exe(exe, args, stdin=data[offset:], env=env)
            path = Path(tmp, 'stdin.bin')
            path.write_bytes(data)
            with open(path, 'rb') as f:
                f.seek(offset)
                results[tag, 'file'] = run_exe(exe, args, stdin_file=f, env=env)
        base = results['legacy', 'pipe']
        for key, value in results.items():
            self.assertEqual(value, base, (name, key))
        if cpython:
            path = Path(tmp, 'stdin.bin')
            with open(path, 'rb') as f:
                f.seek(offset)
                expected = cpython_run(tmp, name, source, args, stdin_file=f)
            self.assertEqual(base[1], expected[1], (name, 'stdout vs CPython'))
            self.assertEqual(base[0], expected[0], (name, 'status vs CPython'))
        if expect_status is not None:
            self.assertEqual(base[0], expect_status, base)
        return base

    def test_every_scan_shape_agrees_with_the_legacy_build_and_cpython(self):
        data = sample(300000)
        with tempfile.TemporaryDirectory() as tmp:
            for name, source in ALL:
                with self.subTest(program=name):
                    self.agree(tmp, name, source, data=data, env=FORCE)
                    self.agree(tmp, name, source, data=data)

    def test_inputs_of_every_size_and_ending(self):
        with tempfile.TemporaryDirectory() as tmp:
            for k, data in enumerate((b'', b'\n', b'>', b'A\n', b'x' * 4095, b'x' * 4096 + b'\n', sample(8193),
                                      sample(40000, 3), b'\n' * 5000, b'>' + b'ACGT' * 9000)):
                with self.subTest(size=len(data), k=k):
                    for name, source in (('lines', LINES), ('find', FIND), ('for_range', FOR_RANGE)):
                        self.agree(tmp, name, source, data=data, env=FORCE)

    def test_an_offset_that_is_not_page_aligned(self):
        data = sample(100000)
        with tempfile.TemporaryDirectory() as tmp:
            for offset in (1, 100, 4095, 4096, 4097, 50001):
                with self.subTest(offset=offset):
                    self.agree(tmp, 'lines', LINES, data=data, offset=offset, env=FORCE)
                    self.agree(tmp, 'limited', LIMITED, data=data, offset=offset, env=FORCE)

    def test_a_limited_read_then_the_rest_then_end_of_file(self):
        data = sample(20000)
        with tempfile.TemporaryDirectory() as tmp:
            base = self.agree(tmp, 'limited', LIMITED, data=data, env=FORCE)
            self.assertEqual(base[0], 0)
            self.assertIn(b' 0\n', base[1][-4:])

    def test_a_text_read_before_a_binary_read_fails_like_the_legacy_build(self):
        data = b'first line\n' + sample(20000)
        with tempfile.TemporaryDirectory() as tmp:
            base = self.agree(tmp, 'text_first', TEXT_FIRST, data=data, env=FORCE, cpython=False)
            self.assertNotEqual(base[0], 0)

    def test_file_reads(self):
        data = sample(150000)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, 'in.bin')
            for size in (0, 1, 5000, len(data)):
                path.write_bytes(data[:size])
                for name, source in (('file_scan', FILE_SCAN), ('file_call', FILE_CALL), ('repeat', REPEAT)):
                    with self.subTest(program=name, size=size):
                        exes = self.build(tmp, name, source)
                        runs = {tag: run_exe(exe, [path], env=FORCE) for tag, exe in exes.items()}
                        for tag, value in runs.items():
                            self.assertEqual(value, runs['legacy'], (name, tag))
                        expected = cpython_run(tmp, name, source, [path])
                        self.assertEqual(runs['ir'][1], expected[1])

    def test_a_missing_file_is_the_legacy_os_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            exes = self.build(tmp, 'file_scan', FILE_SCAN)
            runs = {tag: run_exe(exe, [Path(tmp, 'absent')], env=FORCE) for tag, exe in exes.items()}
            self.assertNotEqual(runs['legacy'][0], 0)
            for tag, value in runs.items():
                self.assertEqual(value, runs['legacy'], tag)

    def test_an_exception_out_of_the_scan_unmaps_in_both_modes(self):
        data = (b'abcdefg!' * 3000) + b'tail'
        with tempfile.TemporaryDirectory() as tmp:
            for limit in (0, 100, 10 ** 9):
                with self.subTest(limit=limit):
                    self.agree(tmp, 'raising', RAISING, args=(limit,), data=data, env=FORCE)

    def test_a_large_input_costs_a_fraction_of_the_input_in_peak_memory(self):
        data = sample(24 * 1024 * 1024, 11)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, 'big.bin')
            path.write_bytes(data)
            peaks = {}
            for name, source in (('lines', LINES), ('for_range', FOR_RANGE)):
                exes = self.build(tmp, name, source)
                outs = {}
                for tag in ('legacy', 'ir'):
                    for mode in ('file', 'pipe'):
                        # a fresh process per measurement: ru_maxrss of the children is a running maximum
                        cmd = ['/usr/bin/time', '-f', '%M', str(exes[tag])]
                        if mode == 'file':
                            with open(path, 'rb') as f:
                                r = subprocess.run(cmd, stdin=f, capture_output=True, timeout=300)
                        else:
                            r = subprocess.run(cmd, input=data, capture_output=True, timeout=300)
                        outs[tag, mode] = (r.stdout, int(r.stderr.decode().strip().splitlines()[-1]))
                self.assertEqual(len({v[0] for v in outs.values()}), 1, name)
                legacy_kb = outs['legacy', 'file'][1]
                self.assertLess(outs['ir', 'file'][1], 0.5 * legacy_kb, (name, outs))
                self.assertGreater(outs['ir', 'pipe'][1], 0.9 * legacy_kb, (name, outs))     # a pipe is read as before
                peaks[name] = {k: v[1] for k, v in outs.items()}
        self.assertTrue(peaks)

    @unittest.skipUnless(shutil.which('gcc'), 'no gcc')
    def test_sanitizers_report_nothing_on_the_ir_builds(self):
        data = sample(60000, 5)
        path_args = None
        for name, source, args in (('lines', LINES, ()), ('for_range', FOR_RANGE, ()), ('find', FIND, ()),
                                   ('slices', SLICES, ()), ('limited', LIMITED, ()), ('raising', RAISING, (100,)),
                                   ('file_scan', FILE_SCAN, None), ('repeat', REPEAT, None)):
            with self.subTest(program=name), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp, 'in.bin')
                path.write_bytes(data)
                run_args = args if args is not None else (path,)
                results = {}
                for tag, env in (('legacy', {'AIL_IR': '0'}), ('ir', {'AIL_IR': 'verify'}),
                                 ('ir-checked', {'AIL_IR': 'verify', 'AIL_IR_EXC': 'checked'})):
                    built, _, _ = compile_program(tmp, name, 'import sys\n' + source, tag, env, debug=True)
                    self.assertEqual(built.returncode, 0, built.stderr)
                    san = Path(tmp, name + '.' + tag + '.san')
                    cc = subprocess.run(['gcc', '-O1', '-g', '-fsanitize=address,undefined',
                                         '-fno-sanitize-recover=undefined', '-fno-omit-frame-pointer', '-pthread',
                                         str(Path(tmp, '%s.%s.d' % (name, tag), 'program.c')), '-lm', '-o', str(san)],
                                        capture_output=True, text=True)
                    self.assertEqual(cc.returncode, 0, cc.stderr[-2000:])
                    env_run = dict(FORCE, ASAN_OPTIONS=ASAN_DETECT_LEAKS + ':abort_on_error=0',
                                   UBSAN_OPTIONS='print_stacktrace=1:halt_on_error=1')
                    with open(Path(tmp, 'stdin.bin'), 'wb') as f:
                        f.write(data)
                    with open(Path(tmp, 'stdin.bin'), 'rb') as f:
                        results[tag] = run_exe(san, run_args, stdin_file=f, env=env_run)
                for tag in ('ir', 'ir-checked'):
                    status, stdout, stderr = results[tag]
                    err = stderr.decode(errors='replace')
                    self.assertNotIn('runtime error', err, (name, tag))
                    self.assertNotIn('AddressSanitizer', err, (name, tag, err[-600:]))
                    self.assertNotIn('LeakSanitizer', err.replace('LeakSanitizer is disabled', ''), (name, tag))
                    self.assertEqual((status, stdout), results['legacy'][:2], (name, tag))


if __name__ == '__main__':
    unittest.main()
