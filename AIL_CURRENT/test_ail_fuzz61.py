"""fuzz61: every CPython alias of utf-8, ascii and latin-1 reaches the same codec.

An encoding name that is not a literal is looked up at run time. The run-time table in
prelude_bytes only knew a few spellings, so a program that passed an alias through a variable,
a function argument, a list item, an attribute or a dict value printed ``LookupError`` where
CPython encoded or decoded: ``"é".encode("csascii", "ignore")``, ``b"\\xe9".decode("csisolatin1")``
and the utf-8 spellings ``utf8_ucs2`` / ``utf8_ucs4`` were missing. The table now has every
alias from encodings.aliases for those three codecs; safetyrt.ENCODINGS accepts the same
literal spellings instead of refusing them by name.

Both builds (default and AIL_UNIFIED_FORCE=1) must print what CPython prints.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

ALIASES = ("utf-8", "utf8", "u8", "utf", "cp65001", "utf8_ucs2", "utf8_ucs4",
           "ascii", "us-ascii", "us", "646", "ansi_x3.4_1968", "ansi-x3.4-1968",
           "ansi_x3.4_1986", "ansi_x3_4_1968", "cp367", "csascii", "ibm367",
           "iso646_us", "iso_646.irv_1991", "iso_ir_6",
           "latin-1", "latin1", "latin_1", "iso-8859-1", "iso8859", "iso8859_1",
           "iso_8859_1", "iso_8859_1_1987", "8859", "cp819", "l1", "latin",
           "iso_ir_100", "csisolatin1", "ibm819")

ALIAS_MATRIX = '''class Box:
    def __init__(self, name):
        self.name = name


def enc(value, name, errors="strict"):
    return value.encode(name, errors)


def dec(value, name, errors="strict"):
    return value.decode(name, errors)


def main():
    names = %r
    text = "a\\u00e9\\u20ac"
    raw = b"a\\xc3\\xa9\\xe2\\x82\\xac"
    for name in names:
        print("E", name, enc(text, name, "replace").hex(), len(enc(text, name, "replace")))
        print("D", name, repr(dec(raw, name, "replace")))
        try:
            print("S", name, text.encode(name))
        except UnicodeEncodeError:
            print("S", name, "UEE")
        try:
            print("T", name, b"\\xff".decode(name))
        except (UnicodeDecodeError, ValueError) as error:
            print("T", name, type(error).__name__)
    xs = ["csascii", "cp367", "ibm367", "csisolatin1", "ibm819", "utf8_ucs4"]
    d = {"x": "csascii", "y": "csisolatin1", "z": "utf8_ucs2"}
    box = Box("ibm819")
    for i in range(len(xs)):
        print("L", enc("\\u00e9", xs[i], "ignore"), dec(b"\\xe9", xs[i], "ignore"))
    print("A", enc("\\u20ac", box.name, "replace"), dec(b"\\xe9", box.name))
    print("D", enc("\\u00e9", d["x"], "ignore"), dec(b"\\xe9", d["y"]))
    print("F", enc("\\u00e9", d["z"], "ignore"), dec(b"\\xe9", xs[5], "ignore"))
main()
''' % (ALIASES,)

LITERAL_ALIASES = '''def main():
    print("\\u00e9".encode("csascii", "ignore"), "\\u00e9".encode("cp367", "replace"))
    print("\\u00e9".encode("ibm367", "ignore"), "\\u20ac".encode("us_ascii", "replace"))
    print("\\u00e9".encode("iso_646.irv_1991", "ignore"), "\\u00e9".encode("iso_ir_6", "ignore"))
    print(b"\\xe9".decode("csisolatin1"), b"\\xe9".decode("ibm819"))
    print(b"\\xe9".decode("iso_8859_1_1987"), b"\\xe9".decode("iso8859"))
    print("\\u00e9".encode("utf8_ucs2"), "\\u00e9".encode("utf8_ucs4"))
    print(b"\\xc3\\xa9".decode("utf8_ucs2"), b"\\xc3\\xa9".decode("utf8_ucs4"))
    print("".encode("csascii"), b"".decode("csisolatin1"))
    print(b"a\\xffb".decode("utf8_ucs2", "replace"), b"a\\xffb".decode("utf8_ucs2", "ignore"))
main()
'''

REACH = '''class Holder:
    pass


def via_arg(value, name, errors):
    return value.encode(name, errors)


def main():
    holder = Holder()
    holder.enc = "csisolatin1"
    holder.data = b"a\\xffb"
    values = ["\\u00e9", "\\u20ac", "x"]
    names = ["csascii", "csisolatin1", "ibm819"]
    table = {"a": "csascii", "b": "csisolatin1"}
    for i in range(len(values)):
        print(values[i].encode(names[i], "ignore"), via_arg(values[i], names[i], "replace"))
    print(holder.data.decode(holder.enc), via_arg("\\u00e9", holder.enc, "ignore"))
    print(values[1].encode(table["a"], "replace"), holder.data.decode(table["b"], "ignore"))
    bad = "not" + "-a-codec"
    try:
        values[0].encode(bad)
    except LookupError:
        print("LookupError")
    try:
        b"x".decode(bad)
    except LookupError:
        print("LookupError")
    try:
        values[0].encode(5)
    except TypeError:
        print("TypeError")
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


class Fuzz61Aliases(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz61-') as directory:
            want, rc, err = _cpython(directory, slug, text)
            self.assertEqual(rc, 0, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, 0), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_alias_matrix_dynamic(self):
        self.check('aliases', ALIAS_MATRIX)

    def test_alias_matrix_literal(self):
        self.check('literal_aliases', LITERAL_ALIASES)

    def test_alias_through_argument_list_attribute_dict(self):
        self.check('reach', REACH)


if __name__ == '__main__':
    unittest.main()
