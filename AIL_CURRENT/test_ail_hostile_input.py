"""Hostile input through the general and typed paths: parsing and text must not corrupt memory.

The programs read stdin and push it through int()/float() (all bases, huge, signed, underscores,
non-ASCII digits), str split/strip/replace/find/join/format/encode, slicing with computed and
extreme indices, bytes/bytearray operations, ord/chr, dict keys and a hand-written JSON-ish parse.
They are built with AddressSanitizer + UndefinedBehaviorSanitizer on both builds and compared with
CPython on the same bytes.

`REGRESSIONS` holds inputs that once crashed or differed. `test_fuzz` runs a short seeded mutation
fuzz (the same generator as tools/input_fuzz.py) with a 10 s per-run timeout. Differences already
recorded in DIFFERENCES.md (a valid non-BMP UTF-8 sequence, an int beyond int64) are checked by
`test_documented_differences` instead of pretending to match CPython.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PYC = ROOT / 'python' / 'pkg-v12' / 'pyc.py'
HAVE_CC = shutil.which('gcc') is not None
SAN = ['-fsanitize=address,undefined', '-fno-sanitize-recover=undefined',
       '-g', '-fno-omit-frame-pointer']
SAN_ENV = {
    'ASAN_OPTIONS': 'detect_leaks=0:detect_stack_use_after_return=0',
    'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1',
}

PROGRAMS = {
    'numbers': r'''
import sys


def safe(label, fn):
    try:
        print(label, repr(fn()))
    except Exception as e:
        print(label, type(e).__name__, str(e))


def main():
    raw = sys.stdin.buffer.read()
    text = raw.decode("utf-8", "replace")
    for s in text.split("\n"):
        if s == "" and text == "":
            break
        safe("int", lambda: int(s))
        for b in (0, 2, 8, 10, 16, 36):
            safe("intb%d" % b, lambda b=b: int(s, b))
        safe("float", lambda: float(s))
        safe("bytesint", lambda: int(s.encode("utf-8")))
        safe("bytesfloat", lambda: float(s.encode("utf-8")))
        safe("ba_int", lambda: int(bytearray(s.encode("utf-8"))))
        safe("bytes_repr", lambda: repr(s.encode("utf-8")))
        safe("ba_repr", lambda: repr(bytearray(s.encode("utf-8"))))
        safe("bool", lambda: bool(s))
        safe("ord", lambda: (ord(s[0]), chr(ord(s[0]))) if s else None)


main()
''',
    'text': r'''
import sys


def safe(label, fn):
    try:
        print(label, repr(fn()))
    except Exception as e:
        print(label, type(e).__name__, str(e))


def main():
    data = sys.stdin.buffer.read()
    text = data.decode("utf-8", "replace")
    print("len", len(text), repr(text))
    print("split", text.split(), text.split(","), text.split(",", 2), text.rsplit(",", 2),
          text.splitlines(), text.splitlines(True))
    print("strip", text.strip(), text.lstrip("ab \t"), text.rstrip("\x00 "), text.strip("\u00a0"))
    print("replace", text.replace("a", "XY"), text.replace("", "-", 3), text.replace("ab", ""))
    print("find", text.find("a"), text.rfind("a"), text.find("a", 1, -1), text.count("a"),
          text.count(""))
    print("join", "-".join(text.split(",")), text.join(["p", "q"]))
    safe("format", lambda: text.format("A", 2, x=3))
    safe("encode", lambda: (text.encode("utf-8"), text.encode("ascii", "replace"),
                            text.encode("latin-1", "ignore")))
    safe("case", lambda: (text.lower(), text.upper(), text.title(), text.capitalize(),
                          text.swapcase(), text.casefold()))
    safe("pred", lambda: (text.isalpha(), text.isalnum(), text.isdigit(), text.isdecimal(),
                          text.isnumeric(), text.isspace(), text.isascii(), text.isidentifier()))
    n = len(text)
    for a, b, c in [(0, n, 1), (0, n, -1), (n, -n, 2), (-1, None, -2), (None, None, 3),
                    (n + 5, -n - 5, -3), (-10**6, 10**6, 7), (10**15, -10**15, -999)]:
        safe("slice%s" % str(a), lambda a=a, b=b, c=c: text[a:b:c])
        safe("bslice%s" % str(a), lambda a=a, b=b, c=c: data[a:b:c])
    safe("index", lambda: (text[0], text[-1], text[n // 2]))
    safe("ord", lambda: (ord(text[0]), ord(text[-1]), chr(ord(text[0]))))
    safe("dict", lambda: ({text: 1, text[:3]: 2}, sorted({text, text[::-1]})))
    safe("jsonish", lambda: ([x.partition("=") for x in text.split(",")],
                             [x.strip() for x in text.split(",") if x.strip()]))
    specs = ["", ">8", "^9", ",", "_", ",é", "_日", ",\x1f", "_\x1f", ",x", "_x", ",n", "_n", "_b", "s", "d", "q", "\x1f", "\x7f", ".2f"]
    for spec in specs:
        safe("fs", lambda spec=spec: (format(1234567, spec), format(1.5, spec),
                                      format("ab", spec)))
    for fmt, args in (("%d|%s|%05x|%c|%r", (65, "q", 255, 9731, None)),
                      ("%*d|%-*d|%.*f", (5, 1, 4, 2, 2, 3.14159)),
                      ("%s/%r/%x", ("é", "x", 31))):
        safe("pct", lambda fmt=fmt, args=args: fmt % args)


main()
''',
    'binary': r'''
import sys


def main():
    d = sys.stdin.buffer.read()
    print("len", len(d))
    print("repr", repr(d))
    print("split", d.split(b"\x00"), d.split(b"\xff"), d.split(b","), d.split(b",", 2),
          d.rsplit(b",", 2))
    print("strip", d.strip(), d.lstrip(b"\x00 "), d.rstrip(b" \xff"))
    print("replace", d.replace(b"\x00", b"XY"), d.replace(b"", b"-", 3), d.replace(b"ab", b""))
    print("find", d.find(b"\x00"), d.rfind(b"\xff"), d.count(b"\x00"), d.count(b""))
    print("slice", d[0:3], d[::-1], d[1:len(d) // 2], d[-5:], d[100:], d[-100:])
    print("hex", d.hex(), d.hex(" ", 2), d.hex("-", -2))
    print("lines", d.splitlines(), d.splitlines(True))
    print("dec", d.decode("utf-8", "replace"), d.decode("latin-1"))
    try:
        print("strict", d.decode("utf-8"))
    except UnicodeDecodeError as e:
        print("decode", type(e).__name__, str(e))
    a = bytearray(d)
    a.extend(b"zz")
    a[0:1] = b"Q"
    a.reverse()
    print("ba", bytes(a), a.find(b"Q"), a.count(b"Q"), repr(a))
    print("join", b"-".join(d.split(b"\x00")), b"".join([d[:2], d[-2:]]))
    print("cmp", d == bytes(d), d < d + b"x", sorted([d, d[:2], b"", b"a"]))
    for i in range(min(len(d), 8)):
        print("ord", i, d[i], hex(d[i]), chr(d[i]))
    print("concat", d + d[::-1], d * 2 if len(d) < 20 else b"skip")
    print("partition", d.partition(b"\x00"), d.rpartition(b"\x00"))


main()
''',
    'slices': r'''
class Box:
    def __init__(self, v):
        self.v = v


def cut(x, a, b, c):
    return x[a:b:c]


def show(label, x, a, b, c):
    try:
        r = x[a:b:c]
        print(label, a, b, c, repr(r))
    except Exception as e:
        print(label, a, b, c, type(e).__name__, str(e))


def main():
    for x in ["abcdef", b"abcdef"]:
        for a in [None, -10**18, -5, -1, 0, 2, 10**18]:
            for b in [None, -10**18, -1, 0, 3, 10**18]:
                for c in [None, -10**18, -3, -1, 1, 2, 10**18,
                          -9223372036854775807 - 1, 9223372036854775807]:
                    show(type(x).__name__, x, a, b, c)
    for x in [[0, 1, 2, 3, 4, 5]]:
        for a in [None, -10**18, 0, 2, 10**18]:
            for b in [None, -10**18, -1, 3, 10**18]:
                for c in [None, -10**18, -1, 1, 2, 10**18,
                          -9223372036854775807 - 1, 9223372036854775807]:
                    show("list", x, a, b, c)
    for x in [bytearray(b"abcdef")]:
        for a in [None, -10**18, 0, 2, 10**18]:
            for b in [None, -10**18, -1, 3, 10**18]:
                for c in [None, -10**18, -1, 1, 2, 10**18,
                          -9223372036854775807 - 1, 9223372036854775807]:
                    y = x[a:b:c]
                    print("bytearray", a, b, c, repr(bytes(y)))
    a, b, c = None, None, None
    print(cut("abcdef", a, b, c), cut([0, 1, 2], a, b, c), cut(b"abcdef", a, b, c))
    box = Box(None)
    print(cut("abcdef", box.v, box.v, box.v))
    d = {"s": None}
    print(cut("abcdef", d["s"], d["s"], d["s"]))
    xs = [None]
    print(cut("abcdef", xs[0], xs[0], xs[0]))
    print("abc"[None:None:None], "abc"[None:None:-1], [0, 1, 2][None:None:-1],
          b"abc"[None:None:-1], bytes(bytearray(b"abc")[None:None:-1]))
    for x in ["abc", b"abc", [0, 1, 2], bytearray(b"abc")]:
        try:
            print(x[::0])
        except Exception as e:
            print(type(e).__name__, str(e))
    print("step-min", "abcdef"[::-9223372036854775807 - 1],
          [0, 1, 2, 3][::-9223372036854775807 - 1],
          b"abcdef"[::-9223372036854775807 - 1])


main()
''',
}

# (program name, stdin) inputs that previously crashed or differed.
REGRESSIONS = [
    ('slice-none-literal', 'slices', b''),
    ('slice-none-dynamic', 'slices', b''),
    ('slice-step-min', 'slices', b''),
    ('slice-step-zero-message', 'slices', b''),
    ('int-long-nonascii-repr', 'numbers', ('é' * 250 + 'x').encode('utf-8')),
    ('int-long-ascii-repr', 'numbers', b'x' * 5000),
    ('int-underscore-nonascii', 'numbers', '1٢3\n１_２\n١_٢\n'.encode('utf-8')),
    ('int-bytes-nonascii', 'numbers', b'\xc3\xa9\x31\n'),
    ('bytearray-repr-quotes', 'numbers', b"'\""),
    ('format-wide-type', 'text', b''),
    ('format-percent-control', 'text', b''),
    ('invalid-utf8', 'binary', b'\xff\xc0\xaf\xed\xa0\x80\xe4\xb8x\xf0\x9f\x98'),
    ('nul-bytes', 'binary', b'\x00\x00\xff\x00'),
    ('long-invalid-line', 'numbers', b'!' * (1 << 20)),
]

CURATED = [
    b'', b' ', b'\n', b'\x00', b'12 ab 7 \xc3\xa9\n3',
    b'999999999999\n-999999999999\n+7\n1_000\n',
    b'\xff\xc0\xaf\xed\xa0\x80\xe4\xb8x\xf0\x9f\x98',
    b"'\x22\\\t\r\n", b'!' * 100000,
    ('é' * 250 + 'x').encode('utf-8'),
]


def _sanitizers_work():
    if not HAVE_CC:
        return False
    with tempfile.TemporaryDirectory() as d:
        src = Path(d, 'p.c')
        src.write_text('int main(void){return 0;}\n')
        return subprocess.run(['gcc'] + SAN + [str(src), '-o', str(Path(d, 'p'))],
                              capture_output=True).returncode == 0


HAVE_SAN = _sanitizers_work()


@unittest.skipUnless(HAVE_SAN, 'gcc with AddressSanitizer/UndefinedBehaviorSanitizer is required')
class HostileInput(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.work = Path(cls.tmp.name)
        cls.exes = {}
        cls.sources = {}
        for name, source in PROGRAMS.items():
            src = cls.work / (name + '.py')
            src.write_text(source, encoding='utf-8')
            cls.sources[name] = src
            cls.exes[name] = {}
            for mode, general in (('general', True), ('default', False)):
                exe = cls.work / (name + ('_g' if general else '_d'))
                env = dict(os.environ, AIL_NO_CACHE='1', AIL_IR='0',
                           AIL_EXTRA_CFLAGS=' '.join(SAN), **SAN_ENV)
                env.pop('AIL_NO_GENERAL', None)
                cmd = [sys.executable, '-B', str(PYC), str(exe), '--file', str(src)]
                if general:
                    cmd.append('--general-only')
                res = subprocess.run(cmd, cwd=cls.work, capture_output=True, text=True,
                                     timeout=900, env=env)
                if res.returncode:
                    raise AssertionError('build %s %s failed:\n%s' %
                                         (name, mode, res.stderr[-3000:]))
                cls.exes[name][mode] = exe

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_py(self, name, data):
        return subprocess.run([sys.executable, str(self.sources[name])], input=data,
                              capture_output=True, timeout=120)

    def run_ail(self, name, mode, data):
        return subprocess.run([str(self.exes[name][mode])], input=data, capture_output=True,
                              timeout=30, env=dict(os.environ, **SAN_ENV))

    def compare(self, name, data, modes=('general', 'default')):
        want = self.run_py(name, data)
        for mode in modes:
            got = self.run_ail(name, mode, data)
            err = got.stderr.decode('utf-8', 'replace')
            self.assertNotIn('Sanitizer', err, (name, mode, data[:80], err[-2000:]))
            self.assertNotIn('runtime error:', err, (name, mode, data[:80], err[-2000:]))
            self.assertGreaterEqual(got.returncode, 0, (name, mode, data[:80], err[-1000:]))
            self.assertEqual(got.stdout, want.stdout, (name, mode, data[:80], err[-1000:]))
            self.assertEqual(got.returncode, want.returncode, (name, mode, data[:80], err[-1000:]))

    def test_programs(self):
        for name in PROGRAMS:
            for data in CURATED:
                with self.subTest(program=name, data=data[:40]):
                    self.compare(name, data)

    def test_regressions(self):
        for label, name, data in REGRESSIONS:
            with self.subTest(label):
                self.compare(name, data)

    def test_documented_differences(self):
        """DIFFERENCES.md: a valid non-BMP UTF-8 sequence still stops."""
        self.compare('numbers', b'9' * 30)        # exact ints (bigint): an int beyond int64 matches CPython
        for name, data, text in (
                ('binary', b'\xf0\x9f\x98\x80', 'code point above U+FFFF'),):
            for mode in ('general', 'default'):
                got = self.run_ail(name, mode, data)
                self.assertNotEqual(got.returncode, 0, (name, mode))
                self.assertIn(text, got.stderr.decode('utf-8', 'replace'), (name, mode))

    def test_fuzz(self):
        """A short seeded mutation run, < 3 minutes, with the tool's generator."""
        sys.path.insert(0, str(ROOT.parent / 'tools'))
        import input_fuzz
        seeds = [b'', b'\x00', b'\xff', b'\xff' * 32, b'\xc0\xaf', b'\xed\xa0\x80',
                 b'9223372036854775807', b'-9223372036854775808', b'1_000', b'1__0',
                 b'0x10', b'abc,def', b'"k":1', b'  a b  ', b'\xe4\xb8\xad']
        rng = __import__('random').Random(20261025)
        for name in PROGRAMS:
            for i in range(12):
                data = input_fuzz.mutate(rng, seeds, i)
                with self.subTest(program=name, case=i):
                    want = self.run_py(name, data)
                    for mode in ('general', 'default'):
                        got = self.run_ail(name, mode, data)
                        verdict = input_fuzz.classify(want, got)
                        self.assertIn(verdict, (None, 'known'),
                                      (name, mode, i, data[:80], got.stderr[-1000:]))


if __name__ == '__main__':
    unittest.main()
