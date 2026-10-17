"""The C fast paths of json.loads and json.dumps against CPython.

json.loads of a plain document into a declared list / dict is parsed in one pass by the C runtime
(cruntime JF* parts, jsonrt.py FAST_*) and json.dumps of a flat list, a nested list or a str-keyed
dict is built by C appenders (JD* parts). A document the fast path declines -- a syntax error, a
value of another type, NaN, an integer beyond int64 -- takes the scanner and typed parsers, which
produce CPython's error. Here the compiled program (the Python syntax, AIL_NO_GENERAL=1) and
CPython run the same generated documents (valid, mutated, large, with escapes and non-ASCII text)
and print the same bytes: every parse in all four statement shapes (annotated assignment, assignment
to an annotated name, a return, a call argument), every dumps with several option sets, the error
messages included.
"""
import json
import math
import os
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def compile_python(directory, text, name):
    source, exe = Path(directory, name + ".ail"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name,
                            "--syntax", "python", "-o", exe.name], cwd=directory, capture_output=True,
                           text=True, timeout=900, env=dict(os.environ, AIL_NO_GENERAL="1"))
    return built, source, exe


def old_float_repr(v):
    """The digits the runtime's printf-search float printer (ail_fmt_float) writes: the shortest precision whose
    correctly rounded decimal reads back as the same double. It is CPython's repr except for 46 of the
    powers of two, where the interval is lopsided and the nearest decimal of the shortest length falls
    outside it; those keep the printer's answer (json.dumps always agreed with str() here)."""
    if v == 0:
        return "-0.0" if math.copysign(1, v) < 0 else "0.0"
    a = abs(v)
    for p in range(1, 18):
        s = "%.*e" % (p - 1, a)
        if float(s) == a:
            break
    mant, _, ex = s.partition("e")
    digits = mant.replace(".", "").rstrip("0") or "0"
    exp10 = int(ex)
    nd = len(digits)
    if -4 <= exp10 < 16:
        if exp10 >= 0:
            body = "".join(digits[i] if i < nd else "0" for i in range(exp10 + 1)) + "."
            body += digits[exp10 + 1:] if nd > exp10 + 1 else "0"
        else:
            body = "0." + "0" * (-exp10 - 1) + digits
    else:
        body = digits[0] + ("." + digits[1:] if nd > 1 else "") + "e%s%02d" % ("-" if exp10 < 0 else "+", abs(exp10))
    return ("-" if v < 0 else "") + body


def expected_float_repr(v):
    # The runtime float formatter now matches CPython repr for every double (powers of two included).
    return repr(v)


PROGRAM = r'''import json
import sys


def fold(text: str) -> int:
    h = len(text)
    for ch in text:
        h = (h * 131 + ord(ch)) % 1000000007
    return h


def ret_dict(t: str) -> dict[str, int]:
    return json.loads(t)


def ret_floats(t: str) -> list[float]:
    return json.loads(t)


def count_ints(xs: list[int]) -> int:
    n = 0
    for v in xs:
        n = (n * 31 + v % 1000003) % 1000003
    return len(xs) * 7 + n


def count_strs(xs: list[str]) -> int:
    n = 0
    for s in xs:
        n += len(s)
    return n


def main() -> int:
    for line in sys.stdin:
        kind = line[0]
        text = line[1:].rstrip("\n")
        try:
            if kind == "i":
                xs: list[int] = json.loads(text)
                #CHK:chk_int(xs)
                print("i", len(xs), fold(json.dumps(xs)), fold(json.dumps(xs, indent=2)), fold(json.dumps(xs, separators=(",", ":"))))
            elif kind == "I":
                ys: list[int] = []
                ys.append(5)
                ys = json.loads(text)
                #CHK:chk_int(ys)
                print("I", len(ys), fold(json.dumps(ys, indent="\t")))
            elif kind == "A":
                #CHK:chk_int(json.loads(text))
                print("A", count_ints(json.loads(text)))
            elif kind == "R":
                d0 = ret_dict(text)
                #CHK:chk_dict(d0)
                print("R", len(d0), fold(json.dumps(d0)))
            elif kind == "F":
                fs0 = ret_floats(text)
                #CHK:chk_float(fs0)
                print("F", len(fs0), fold(json.dumps(fs0)))
            elif kind == "f":
                fs: list[float] = json.loads(text)
                #CHK:chk_float(fs)
                print("f", len(fs), fold(json.dumps(fs)), fold(json.dumps(fs, indent=1)))
                try:
                    print("f", fold(json.dumps(fs, allow_nan=False)))
                except ValueError as e:
                    print("VE", @MSG@)
            elif kind == "s":
                ss: list[str] = json.loads(text)
                #CHK:chk_str(ss)
                print("s", len(ss), count_strs(ss), fold(json.dumps(ss)), fold(json.dumps(ss, ensure_ascii=False)), fold(json.dumps(ss, indent=2)))
            elif kind == "b":
                bs: list[bool] = json.loads(text)
                #CHK:chk_bool(bs)
                print("b", len(bs), fold(json.dumps(bs)), fold(json.dumps(bs, indent=1)))
            elif kind == "d":
                d: dict[str, int] = json.loads(text)
                #CHK:chk_dict(d)
                print("d", len(d), fold(json.dumps(d)), fold(json.dumps(d, sort_keys=True, indent=2)), fold(json.dumps(d, sort_keys=True, ensure_ascii=False)))
                for k in d:
                    print(k, d[k])
            elif kind == "e":
                e1: dict[str, float] = json.loads(text)
                #CHK:chk_dictf(e1)
                print("e", len(e1), fold(json.dumps(e1)), fold(json.dumps(e1, sort_keys=True, indent=1)))
                try:
                    print("e", fold(json.dumps(e1, allow_nan=False)))
                except ValueError as e:
                    print("VE", @MSG@)
            elif kind == "t":
                t1: dict[str, str] = json.loads(text)
                #CHK:chk_dicts(t1)
                print("t", len(t1), fold(json.dumps(t1)), fold(json.dumps(t1, sort_keys=True, indent=2)), fold(json.dumps(t1, ensure_ascii=False)))
                for k in t1:
                    print(fold(k), fold(t1[k]))
            elif kind == "l":
                g: list[list[int]] = json.loads(text)
                #CHK:chk_ll(g)
                print("l", len(g), fold(json.dumps(g)), fold(json.dumps(g, indent="\t")), fold(json.dumps(g, separators=(",", ":"))))
            elif kind == "m":
                h: list[list[float]] = json.loads(text)
                #CHK:chk_lf(h)
                print("m", len(h), fold(json.dumps(h)), fold(json.dumps(h, indent=2)))
                try:
                    print("m", fold(json.dumps(h, allow_nan=False)))
                except ValueError as e:
                    print("VE", @MSG@)
            elif kind == "n":
                w: list[list[str]] = json.loads(text)
                #CHK:chk_lstr(w)
                print("n", len(w), fold(json.dumps(w)), fold(json.dumps(w, ensure_ascii=False, indent=1)))
            elif kind == "k":
                ks: list[int] = json.loads(text)
                #CHK:chk_int(ks)
                di: dict[int, int] = {}
                for v in ks:
                    di[v] = v % 1000
                print("k", len(di), fold(json.dumps(di)), fold(json.dumps(di, sort_keys=True)))
            else:
                print("?")
        except ValueError as e:
            print("VE", @MSG@)
        except RuntimeError as e:
            print("RT")
    return 0


main()
'''

ORACLE_GUARD = r'''
def _bad(v):
    raise RuntimeError("type")


def _str_ok(s):
    return isinstance(s, str) and not any(0xD800 <= ord(ch) < 0xE000 for ch in s)


def _int_ok(x):
    return type(x) is int and -2 ** 63 <= x < 2 ** 63


def chk_int(xs):
    if not isinstance(xs, list) or not all(_int_ok(x) for x in xs):
        _bad(xs)


def chk_float(xs):
    if not isinstance(xs, list) or any(type(x) is not float for x in xs):
        _bad(xs)


def chk_str(xs):
    if not isinstance(xs, list) or not all(_str_ok(x) for x in xs):
        _bad(xs)


def chk_bool(xs):
    if not isinstance(xs, list) or any(type(x) is not bool for x in xs):
        _bad(xs)


def chk_dict(d):
    if not isinstance(d, dict) or not all(_str_ok(k) and _int_ok(v) for k, v in d.items()):
        _bad(d)


def chk_dictf(d):
    if not isinstance(d, dict) or not all(_str_ok(k) and type(v) is float for k, v in d.items()):
        _bad(d)


def chk_dicts(d):
    if not isinstance(d, dict) or not all(_str_ok(k) and _str_ok(v) for k, v in d.items()):
        _bad(d)


def chk_ll(g):
    if not isinstance(g, list) or not all(isinstance(r, list) and all(_int_ok(x) for x in r) for r in g):
        _bad(g)


def chk_lf(g):
    if not isinstance(g, list) or not all(isinstance(r, list) and all(type(x) is float for x in r) for r in g):
        _bad(g)


def chk_lstr(g):
    if not isinstance(g, list) or not all(isinstance(r, list) and all(_str_ok(x) for x in r) for r in g):
        _bad(g)


'''


def documents(count=9000, seed=2026):
    rng = random.Random(seed)
    alphabet = ["a", "b", "é", "日", "😀", "\\", '"', " ", "z", "0", "/", "\x01", "\x7f", "\t", "\u2028", "\ud7ff", ",", ":"]

    def rstr():
        return "".join(rng.choice(alphabet) for _ in range(rng.choice([0, 0, 1, 2, 5, 12, 40])))

    def rkey():
        return rng.choice(["key%d" % rng.randint(0, 50), rstr(), "k" * rng.randint(0, 30) + str(rng.randint(0, 9))])

    def rint():
        return rng.choice([0, 1, -1, 7, 123456789, -2 ** 63, 2 ** 63 - 1, 2 ** 63, -2 ** 63 - 1, 10 ** 18, -10 ** 18,
                           999999999999999999, 9999999999999999999, 12345678901234567890, rng.randint(-1000, 1000),
                           rng.randint(-10 ** 12, 10 ** 12)])

    def rfloat():
        return rng.choice([0.0, -0.0, 1.5, 1e22, 5e-324, 1.7976931348623157e308, 0.1, 100.0, 1e16, 1e15, 123456.789,
                           float("nan"), float("inf"), float("-inf"), 2.5e-5, rng.uniform(-1e6, 1e6),
                           rng.uniform(-1, 1) * 10 ** rng.randint(-30, 30)])

    def render(obj):
        kw = {"ensure_ascii": rng.random() < 0.5}
        if rng.random() < 0.25:
            kw["separators"] = (rng.choice([",", ", ", " ,", ",\n"]), rng.choice([":", ": ", " : ", "\t:\t"]))
        if rng.random() < 0.15:
            kw["indent"] = rng.choice([0, 1, 2, "\t"])
        text = json.dumps(obj, **kw)
        if rng.random() < 0.1:
            text = " \n" + text + "\r\n\t "
        return text

    def mutate(text):
        if not text:
            return text
        pos = rng.randrange(len(text))
        op = rng.choice(["del", "ins", "rep", "trunc", "dup", "swap"])
        ch = rng.choice(list('[]{},:"\\ 0123456789.eE+-tfnuNI') + ["\\u12", "\\ud83d", "\x01", "é", "\\ud83d\\ude00",
                                                                     "1.5", "01", "-", "NaN", "null", "true", "9" * 20])
        if op == "del":
            return text[:pos] + text[pos + 1:]
        if op == "ins":
            return text[:pos] + ch + text[pos:]
        if op == "rep":
            return text[:pos] + ch + text[pos + 1:]
        if op == "trunc":
            return text[:pos]
        if op == "swap" and pos + 1 < len(text):
            return text[:pos] + text[pos + 1] + text[pos] + text[pos + 2:]
        return text[:pos] + text[pos:pos + 3] + text[pos:]

    def ints(n):
        return [rint() for _ in range(n)]

    lines = []
    for _ in range(count):
        kind = rng.choice("iiIAkfsbddettRFllmn")
        n = rng.choice([0, 1, 2, 3, 5, 8])
        if kind in "iIAk":
            obj = ints(n)
        elif kind in "fF":
            obj = [rfloat() for _ in range(n)]
        elif kind == "s":
            obj = [rstr() for _ in range(n)]
        elif kind == "b":
            obj = [rng.random() < 0.5 for _ in range(n)]
        elif kind in "dR":
            obj = {rkey(): rint() for _ in range(n)}
        elif kind == "e":
            obj = {rkey(): rfloat() for _ in range(n)}
        elif kind == "t":
            obj = {rkey(): rstr() for _ in range(n)}
        elif kind == "l":
            obj = [ints(rng.randint(0, 4)) for _ in range(n)]
        elif kind == "m":
            obj = [[rfloat() for _ in range(rng.randint(0, 4))] for _ in range(n)]
        else:
            obj = [[rstr() for _ in range(rng.randint(0, 3))] for _ in range(n)]
        text = render(obj)
        # a document of another shape now and then: the declared type does not fit
        if rng.random() < 0.06:
            text = render(rng.choice([ints(3), {"a": 1}, [[1], [2]], "x", 5, None, [1.5, 2], {"a": "b"}, [True], [[]]]))
        for _ in range(rng.choice([0, 0, 0, 0, 1, 1, 2])):
            text = mutate(text)
        text = text.replace("\n", "\\n").replace("\r", "\\r")
        lines.append(kind + text)
    # large documents: the growth paths of the lists, dicts and buffers
    big = random.Random(5)
    lines.append("i" + json.dumps([big.randint(-10 ** 9, 10 ** 9) for _ in range(30000)]))
    lines.append("f" + json.dumps([big.uniform(-1e6, 1e6) for _ in range(5000)]))
    lines.append("d" + json.dumps({"key%d" % k: big.randint(-10 ** 9, 10 ** 9) for k in range(20000)}))
    lines.append("e" + json.dumps({"k%d" % k: big.uniform(-1, 1) for k in range(3000)}, indent=1).replace("\n", " "))
    lines.append("t" + json.dumps({"k%d" % k: "v" * (k % 7) + "é" for k in range(3000)}))
    lines.append("s" + json.dumps(["w%d é" % k for k in range(8000)]))
    lines.append("l" + json.dumps([[big.randint(-99, 99) for _ in range(big.randint(0, 9))] for _ in range(3000)]))
    lines.append("m" + json.dumps([[big.uniform(-9, 9) for _ in range(big.randint(0, 5))] for _ in range(800)]))
    lines.append("k" + json.dumps([big.randint(-10 ** 6, 10 ** 6) for _ in range(3000)]))
    lines.append("d" + '{"dup": 1, "other": 2, "dup": 3}')
    lines.append("d" + "{" + ",".join('"key%d":%d' % (k, k) for k in range(200)) + ',"key7":-1}')
    return ("\n".join(lines) + "\n").encode()


class JsonFastTests(unittest.TestCase):
    def build(self, text, name):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        built, _, exe = compile_python(directory.name, text, name)
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        return exe

    def same(self, ran, expected, note=""):
        if ran.returncode == 0 and ran.stdout == expected.stdout:
            return
        got, want = ran.stdout.split(b"\n"), expected.stdout.split(b"\n")
        k = next((i for i in range(min(len(got), len(want))) if got[i] != want[i]), min(len(got), len(want)))
        self.fail("exit %d, first difference at output line %d: got %r, want %r (%s)" % (
            ran.returncode, k, got[k][:300] if k < len(got) else None, want[k][:300] if k < len(want) else None, note))

    def run_built(self, exe, oracle_text, stdin):
        ran = subprocess.run([str(exe)], input=stdin, capture_output=True, timeout=300)
        expected = subprocess.run([sys.executable, "-c", oracle_text], input=stdin, capture_output=True, timeout=300)
        self.assertEqual(expected.returncode, 0, expected.stderr)
        return ran, expected

    def run_both(self, text, name, stdin, oracle_text):
        with tempfile.TemporaryDirectory() as directory:
            built, source, exe = compile_python(directory, text, name)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            oracle = Path(directory, name + "_oracle.py")
            oracle.write_text(oracle_text, encoding="utf-8")
            ran = subprocess.run([str(exe)], input=stdin, capture_output=True, timeout=300)
            expected = subprocess.run([sys.executable, str(oracle)], input=stdin, capture_output=True, timeout=300)
            self.assertEqual(expected.returncode, 0, expected.stderr)
            return ran, expected

    def test_generated_documents_match_cpython(self):
        docs = documents()
        ail = PROGRAM.replace("@MSG@", "e.message")
        py = PROGRAM.replace("@MSG@", "str(e)").replace("#CHK:", "")
        py = py.replace("def main()", ORACLE_GUARD + "def main()", 1)
        ran, expected = self.run_both(ail, "json_fast_fuzz", docs, py)
        self.same(ran, expected, ran.stderr[:500])
        lines = expected.stdout.split(b"\n")
        self.assertGreater(len(lines), 9000)
        # the generator reaches every outcome: parsed, syntax error, wrong type
        self.assertGreater(sum(1 for line in lines if line.startswith(b"VE")), 500)
        self.assertGreater(sum(1 for line in lines if line.startswith(b"RT")), 100)
        self.assertGreater(sum(1 for line in lines if line[:1] in (b"i", b"d", b"l", b"s", b"f", b"e", b"t", b"m", b"n", b"b")), 2000)
        self.assertIn(b"Out of range float values are not JSON compliant", expected.stdout)

    def test_returns_and_arguments_and_reassignment(self):
        text = r'''import json
import sys


def loads_ints(t: str) -> list[int]:
    return json.loads(t)


def total(xs: list[int]) -> int:
    n = 0
    for v in xs:
        n = (n + v % 1000003) % 1000003
    return n


def main() -> int:
    for line in sys.stdin:
        t = line.rstrip("\n")
        try:
            a = loads_ints(t)
            print(len(a), total(a), total(json.loads(t)))
            b: list[int] = [9]
            for r in range(3):
                b = json.loads(t)
                b.append(r)
            print(len(b), b[len(b) - 1], json.dumps(b))
        except ValueError as e:
            print("VE", e.message)
    return 0


main()
'''
        stdin = b'[1, 2, 3]\n[]\n [ -5 , 0 ] \n[1, 2\n[1.5]\n[1e3]\n[9223372036854775807, -9223372036854775808]\n[9223372036854775808]\n'
        oracle = text.replace("e.message", "str(e)")
        # CPython happily returns floats and big ints; the compiled program refuses them, so the oracle
        # only gets the lines both accept
        accepted = b'[1, 2, 3]\n[]\n [ -5 , 0 ] \n[1, 2\n[9223372036854775807, -9223372036854775808]\n'
        ran, expected = self.run_both(text, "json_fast_forms", accepted, oracle)
        self.same(ran, expected, ran.stderr[:500])
        ran, _ = self.run_both(text, "json_fast_forms_bad", stdin, oracle)
        self.assertNotEqual(ran.returncode, 0)
        self.assertIn(b"declared type needs", ran.stderr)

    def test_json_load_of_stdin(self):
        text = r'''import json
import sys


def main() -> int:
    d: dict[str, int] = json.load(sys.stdin)
    print(len(d), json.dumps(d, sort_keys=True))
    return 0


main()
'''
        exe = self.build(text, "json_fast_load")
        for stdin in (b'{"b": 2, "a": 1}', b' {} \n', b'{"a": 1,}'):
            ran = subprocess.run([str(exe)], input=stdin, capture_output=True, timeout=60)
            try:
                want = json.loads(stdin)
                self.assertEqual((ran.returncode, ran.stdout), (0, ("%d %s\n" % (len(want), json.dumps(want, sort_keys=True))).encode()))
            except ValueError:
                self.assertNotEqual(ran.returncode, 0)
                self.assertIn(b"Expecting property name enclosed in double quotes", ran.stderr)

    def test_local_containers_filled_in_place_do_not_leak_between_loads(self):
        # the same annotated locals are loaded again and again: each load starts empty and the container
        # is the program's own afterwards
        text = r'''import json
import sys


def main() -> int:
    for line in sys.stdin:
        t = line.rstrip("\n")
        d: dict[str, int] = {"stale": 1}
        d = json.loads(t)
        d["after"] = len(d)
        xs: list[int] = [7]
        xs = json.loads("[" + str(len(d)) + "]")
        xs.append(len(xs))
        print(len(d), json.dumps(d, sort_keys=True), json.dumps(xs))
    return 0


main()
'''
        stdin = b'{"a": 1}\n{}\n{"b": 2, "a": 1, "b": 3}\n'
        ran, expected = self.run_both(text, "json_fast_local", stdin, text)
        self.same(ran, expected, ran.stderr[:500])

    def test_error_after_a_valid_prefix_is_cpythons_error(self):
        # the fast path may have parsed most of the document when it gives up: a syntax error still comes
        # from the scanner with CPython's text and position, a value of another type is the loud error
        text = r'''import json
import sys


def main() -> int:
    text = sys.stdin.read()
    try:
        d: dict[str, int] = json.loads(text)
        print(len(d))
    except ValueError as e:
        print(e.message)
    return 0


main()
'''
        oracle = text.replace("e.message", "str(e)")
        exe = self.build(text, "json_fast_prefix")
        rows = ", ".join('"k%d": %d' % (k, k) for k in range(3000))
        for tail in ('}x', ', "z": }', ', "z"', ', }', '', ', "z": 01}', ', "z": [}', ', "z": "unterminated}', ', "z": 1.}'):
            stdin = ("{" + rows + tail).encode()
            ran, expected = self.run_built(exe, oracle, stdin)
            self.same(ran, expected, (tail, ran.stderr[:300]))
            self.assertTrue(expected.stdout.startswith(b"Ex") or expected.stdout.startswith(b"Unt"), expected.stdout)
        for tail in (', "z": 1.5}', ', "z": 99999999999999999999999}', ', "z": NaN}', ', "k1": "s"}', ', "z": null}', ', "z": [1]}'):
            stdin = ("{" + rows + tail).encode()
            ran, _ = self.run_built(exe, oracle, stdin)
            self.assertNotEqual(ran.returncode, 0, tail)
            self.assertIn(b"declared type needs", ran.stderr, tail)

    def test_float_repr_round_trips_like_cpython(self):
        # json.dumps writes the shortest digits that read back as the same double (the float printer of
        # cruntime JDFLOATS, which is not printf): every line is CPython's own rendering of its floats, so
        # parsing it and dumping it again must give the line back byte for byte
        import struct
        rng = random.Random(11)
        values = [0.0, -0.0, 1.0, 0.1, 0.5, 1e22, 1e23, 1e16, 1e15, 1e-5, 1e-4, 123456789012345678.0, 5e-324,
                  2.2250738585072014e-308, 1.7976931348623157e308, 9007199254740993.0, 2.0 ** 53, 2.0 ** -1074,
                  4.35, 2.675, 0.3, 100.0, 12345.678]
        values += [2.0 ** k for k in range(-1074, 1024)] + [-(2.0 ** k) for k in range(-1074, 1024, 7)]
        values += [10.0 ** k for k in range(-323, 309)] + [float("%de%d" % (d, k)) for k in range(-320, 300, 3) for d in (1, 5, 9)]
        for _ in range(60000):
            kind = rng.randrange(6)
            if kind == 0:
                bits = rng.getrandbits(64)
                v = struct.unpack("<d", struct.pack("<Q", bits))[0]
                if v != v or v in (float("inf"), float("-inf")):
                    continue
            elif kind == 1:
                v = float(rng.randint(-10 ** 15, 10 ** 15))
            elif kind == 2:
                v = round(rng.uniform(-1000, 1000), rng.randint(0, 6))
            elif kind == 3:
                v = rng.uniform(-1, 1) * 10.0 ** rng.randint(-30, 30)
            elif kind == 4:
                v = rng.randint(1, 10 ** 9) / rng.randint(1, 10 ** 6)
            else:
                v = float("%d.%de%d" % (rng.randint(0, 99999), rng.randint(0, 99999999), rng.randint(-40, 40)))
            values.append(v)
        chunks = [values[k:k + 40] for k in range(0, len(values), 40)]
        lines = [json.dumps(chunk) for chunk in chunks]
        text = r'''import json
import sys


def main() -> int:
    for line in sys.stdin:
        fs: list[float] = json.loads(line.rstrip("\n"))
        print(json.dumps(fs))
        d: dict[str, float] = {}
        for i in range(len(fs)):
            d["k" + str(i)] = fs[i]
        print(len(json.dumps(d)), len(json.dumps(d, sort_keys=True, indent=1)))
    return 0


main()
'''
        stdin = ("\n".join(lines) + "\n").encode()
        exe = self.build(text, "json_fast_floats")
        ran = subprocess.run([str(exe)], input=stdin, capture_output=True, timeout=300)
        self.assertEqual(ran.returncode, 0, ran.stderr[:300])
        got = ran.stdout.split(b"\n")
        for k, chunk in enumerate(chunks):
            reprs = [expected_float_repr(v) for v in chunk]
            self.assertEqual(got[2 * k], ("[" + ", ".join(reprs) + "]").encode(), "line %d" % k)
            plain = "{" + ", ".join('"k%d": %s' % (i, r) for i, r in enumerate(reprs)) + "}"
            order = sorted(range(len(reprs)), key=lambda i: "k%d" % i)
            pretty = "{\n" + ",\n".join(' "k%d": %s' % (i, reprs[i]) for i in order) + "\n}"
            self.assertEqual(got[2 * k + 1], ("%d %d" % (len(plain), len(pretty))).encode(), "line %d" % k)

    def test_dumps_of_a_str_keyed_dict_is_sorted_like_cpython(self):
        text = r'''import json
import sys


def main() -> int:
    d: dict[str, int] = {}
    for line in sys.stdin:
        d[line.rstrip("\n")] = len(d)
    print(json.dumps(d, sort_keys=True))
    print(json.dumps(d, sort_keys=True, ensure_ascii=False, indent=1))
    print(json.dumps(d))
    return 0


main()
'''
        keys = ["b", "a", "ab", "", "é", "z", "日本", "😀", "a\u0000b", "a\u0000", "Z", "aa", "key10", "key9", "key1", "\ufb01", "\U0010ffff",
                "\uffff", "ab\u00e9", "ab\u00ea", "abcdefgh", "abcdefghi", "abcdefg", "abcdefgh\u0000", "x" * 40, "x" * 39 + "y"]
        stdin = ("\n".join(k for k in keys if "\u0000" not in k) + "\n").encode()
        ran, expected = self.run_both(text, "json_fast_sorted", stdin, text)
        self.same(ran, expected, ran.stderr[:500])


if __name__ == "__main__":
    unittest.main()
