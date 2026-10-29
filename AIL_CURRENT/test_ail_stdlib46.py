"""Library batch 6: unicodedata.name / category / normalize (NFC, NFD) / unidata_version, compared with
CPython 3.12 on both builds, plus the named compile-time refusals.

The module is lowered onto prelude_unicodedata.py, generated from CPython's own unicodedata data
(tools/gen_unicodedata.py): category ranges, canonical decomposition / combining class / composition
tables and a front-coded name table; Hangul syllables and the algorithmic ideograph names are computed
by rule.  A sweep over every BMP code point (except the surrogate range and seven CJK compatibility
ideographs recorded in DIFFERENCES) checks category, name, NFD and NFC; a second program drives the
supported functions through an argument, a list item, an attribute and a dict value.

Everything else is refused by name at compile time: lookup / decimal / digit / numeric and the other
queries, NFKC / NFKD and a form computed at run time, keyword arguments (CPython takes these
positional-only), a binding that shadows an imported unicodedata name or the module alias, and a
literal CJK compatibility ideograph whose canonical decomposition is above U+FFFF, which the 16-bit
v2 runtime cannot hold.  Such a character that only reaches normalize at run time raises the same
named error instead of returning the BMP character unchanged; a shadowed from-import is left as
written and matches CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

MATCHES = r'''import unicodedata


def mix(h: int, s: str) -> int:
    for ch in s:
        h = (h * 131 + ord(ch)) % 1000000007
    return h


def describe(ch: str) -> str:
    return unicodedata.category(ch) + ":" + unicodedata.name(ch, "unnamed")


class Holder:
    def __init__(self, ch: str) -> None:
        self.ch: str = ch


def main() -> None:
    for ch in "AéÅǛắe\u0301\u00c5\u1e9b\uac00\u1100\u1161\u11a8Ǆ好\u0378":
        print(hex(ord(ch)), unicodedata.category(ch), unicodedata.name(ch, "unnamed"))
    print(unicodedata.name("\x00", "missing"), unicodedata.name("\x00", 42))
    print(unicodedata.name("好", "not used"), unicodedata.name("Ǆ"))
    cases = [
        "A\u030a", "\u00c5", "\u212b", "e\u0301", "\u00e9", "\u1e9b\u0323",
        "\u1e0b\u0323", "q\u0307\u0323", "a\u0315\u0300", "\u0344", "\u0f73",
        "\u2adc", "\uac00", "\uac01", "\u1100\u1161\u11a8", "\u1100\u1161",
        "\u1112\u1172\u11ab", "\ufb01", " \u0301", "\u0b47\u0b3e", "\u0bc6\u0bbe",
        "\u0cc6\u0cc2", "\u0d46\u0d57", "\u1025\u102e", "\u1b05\u1b35",
        "\uac00\u11a8", "\u1100\uac00", "",
    ]
    for s in cases:
        nfc = unicodedata.normalize("NFC", s)
        nfd = unicodedata.normalize("NFD", s)
        print(len(s), repr(nfc), len(nfc), repr(nfd), len(nfd))
    mixed = "\u00e9\u0323\u0307\uac00A\u030a"
    print(repr(unicodedata.normalize("NFC", mixed)))
    print(repr(unicodedata.normalize("NFD", mixed)))
    arg = "é"
    print(describe(arg))
    for x in ["A", "\u00c5", "\uac00"]:
        print(describe(x))
    h = Holder("\u1e9b")
    print(describe(h.ch))
    table = {}
    table["k"] = "\u212b"
    print(describe(table["k"]))
    print([unicodedata.category("!"), unicodedata.name("!", "none")])
    for bad in (65, None, "ab", ""):
        try:
            print(unicodedata.name(bad))
        except Exception as e:
            print(type(e).__name__, str(e))
    try:
        print(unicodedata.name("\x00"))
    except Exception as e:
        print(type(e).__name__, str(e))
    for bad in (65, None, "ab"):
        try:
            print(unicodedata.category(bad))
        except Exception as e:
            print(type(e).__name__, str(e))
    print(unicodedata.unidata_version)
    cats = {}
    name_len = 0
    name_hash = 0
    nfd_hash = 0
    nfc_hash = 0
    nfd_len = 0
    nfc_len = 0
    cp = 0
    while cp < 0x10000:
        if not (0xD800 <= cp <= 0xDFFF) and cp not in (
                0xFA6C, 0xFACF, 0xFAD0, 0xFAD1, 0xFAD5, 0xFAD6, 0xFAD7):
            ch = chr(cp)
            c = unicodedata.category(ch)
            cats[c] = cats.get(c, 0) + 1
            n = unicodedata.name(ch, "?")
            name_len += len(n)
            name_hash = mix(name_hash, n)
            d = unicodedata.normalize("NFD", ch)
            nfd_len += len(d)
            nfd_hash = mix(nfd_hash, d)
            c2 = unicodedata.normalize("NFC", ch)
            nfc_len += len(c2)
            nfc_hash = mix(nfc_hash, c2)
        cp += 1
    for key in sorted(cats):
        print(key, cats[key])
    print(name_len, name_hash)
    print(nfd_len, nfd_hash)
    print(nfc_len, nfc_hash)


main()
'''

FROM_IMPORT = r'''from unicodedata import category, name, normalize, unidata_version
from unicodedata import name as uname


def main() -> None:
    print(category("A"), category("é"))
    print(name("A"), uname("\x00", "none"))
    print(repr(normalize("NFC", "e\u0301")), repr(normalize("NFD", "\u00e9")))
    print(unidata_version)


main()
'''

REFUSED = {
    'lookup': ('import unicodedata\n\n\ndef main() -> None:\n'
               '    print(unicodedata.lookup("LATIN SMALL LETTER A"))\n\n\nmain()\n',
               'unicodedata.lookup'),
    'nfkc': ('import unicodedata\n\n\ndef main() -> None:\n'
             '    print(unicodedata.normalize("NFKC", "\ufb01"))\n\n\nmain()\n',
             "only the literal forms 'NFC' and 'NFD'"),
    'computed_form': ('import unicodedata\n\n\ndef main() -> None:\n    form = "NFC"\n'
                      '    print(unicodedata.normalize(form, "e\\u0301"))\n\n\nmain()\n',
                      'a form computed at run time'),
    'keyword': ('import unicodedata\n\n\ndef main() -> None:\n'
                '    print(unicodedata.name("\\x00", default="none"))\n\n\nmain()\n',
                'takes no keyword arguments'),
    'astral_decomp': ('import unicodedata\n\n\ndef main() -> None:\n'
                      '    print(unicodedata.normalize("NFD", "\ufa6c"))\n\n\nmain()\n',
                      'above U+FFFF'),
    'astral_decomp_value': (r'''import unicodedata


def main() -> None:
    s = "\ufa6c"
    print(repr(unicodedata.normalize("NFD", s)))


main()
''', 'on a value that may hold U+FA6C'),
    'rebind_module_alias': (r'''import unicodedata


class Box:
    def name(self, x: str) -> str:
        return "box:" + x


unicodedata = Box()


def main() -> None:
    print(unicodedata.name("A"))


main()
''', 'binds the name unicodedata itself'),
}

REBIND_LOCAL = r'''from unicodedata import name


def name(x: str) -> str:
    return "local:" + x


def main() -> None:
    print(name("A"))


main()
'''

RUNTIME_ASTRAL = r'''import sys
import unicodedata


def main() -> None:
    s = sys.stdin.read()
    print(repr(unicodedata.normalize("NFD", s)))


main()
'''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=300,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


def _build(directory, name, text, general):
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
                           capture_output=True, text=True, timeout=1800, env=env)
    return built, exe


class Stdlib46Tests(unittest.TestCase):
    def check_matches(self, text, name):
        with tempfile.TemporaryDirectory(prefix='ail-stdlib46-') as directory:
            want, want_rc, err = _cpython(directory, name, text)
            self.assertEqual(want_rc, 0, err)
            for general in (True, False):
                built, exe = _build(directory, '%s_%s' % (name, 'g' if general else 'd'), text, general)
                output = built.stdout + built.stderr
                self.assertEqual(built.returncode, 0, 'general=%s\n%s' % (general, output[-4000:]))
                got = subprocess.run([str(exe)], capture_output=True, timeout=300, cwd=directory)
                self.assertEqual(got.returncode, want_rc, 'general=%s\n%s' % (general, got.stderr[-2000:]))
                self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want,
                                 'general=%s\n%s' % (general, output[-2000:]))

    def test_matches_cpython_on_both_builds(self):
        self.check_matches(MATCHES, 'matches')

    def test_from_import_matches_cpython_on_both_builds(self):
        self.check_matches(FROM_IMPORT, 'from_import')

    def test_rebound_from_import_is_left_as_written(self):
        self.check_matches(REBIND_LOCAL, 'rebind_local')

    def test_runtime_astral_value_raises_a_named_error(self):
        with tempfile.TemporaryDirectory(prefix='ail-stdlib46-') as directory:
            for general in (True, False):
                built, exe = _build(directory, 'runtime_astral_%s' % ('g' if general else 'd'), RUNTIME_ASTRAL, general)
                output = built.stdout + built.stderr
                self.assertEqual(built.returncode, 0, 'general=%s\n%s' % (general, output[-4000:]))
                got = subprocess.run([str(exe)], input='\ufa6c\n'.encode('utf-8'), capture_output=True,
                                     timeout=300, cwd=directory)
                self.assertNotEqual(got.returncode, 0, 'general=%s ran the unsupported value' % general)
                self.assertIn(b'above U+FFFF', got.stderr, 'general=%s\n%s' % (general, got.stderr[-2000:]))
                self.assertIn(b'U+FA6C', got.stderr, 'general=%s\n%s' % (general, got.stderr[-2000:]))

    def test_unsupported_forms_are_refused_by_name(self):
        for slug, (text, wanted) in REFUSED.items():
            for general in (True, False):
                with self.subTest(slug=slug, general=general):
                    with tempfile.TemporaryDirectory(prefix='ail-stdlib46-') as directory:
                        built, exe = _build(directory, slug, text, general)
                        output = built.stdout + built.stderr
                        self.assertNotEqual(built.returncode, 0, 'general=%s\n%s' % (general, output[-4000:]))
                        self.assertFalse(exe.exists(), '%s (general=%s) built an executable' % (slug, general))
                        self.assertIn(wanted, output, '%s (general=%s)\n%s' % (slug, general, output[-4000:]))


if __name__ == '__main__':
    unittest.main()
