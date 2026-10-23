"""Library batch 6: `ipaddress.IPv4Address` and the pure-Python `urllib.parse` pieces, against CPython.

Every program is ordinary Python. CPython runs it as the oracle and both compiled builds (the default and
AIL_UNIFIED_FORCE=1) must print the same bytes. The preludes are also run under CPython, so the source the
compiler injects is the source the test compares. Unsupported names are refused by name, with a note.
"""
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load_prelude(name):
    spec = importlib.util.spec_from_file_location('_prelude_' + name, ROOT / 'python' / 'pkg-v12' / ('prelude_%s.py' % name))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


IPADDRESS = r"""
import ipaddress as ipa
from ipaddress import IPv4Address as A


class Holder:
    def __init__(self, a):
        self.a = a


def first(addrs):
    return addrs[0]


def main() -> None:
    xs: list[ipa.IPv4Address] = [A("10.1.2.3"), A("10.1.2.4"), A("127.0.0.1"), A("8.8.8.8")]
    for a in xs:
        print(str(a), repr(a), int(a), a.version, a.max_prefixlen, a.compressed, a.exploded, a.packed.hex(),
              a.is_private, a.is_global, a.is_loopback, a.is_link_local, a.is_multicast, a.is_unspecified,
              a.is_reserved, a.reverse_pointer)
    print(first(xs), sorted(xs)[0], len(set(xs)))
    h = Holder(A("8.8.4.4"))
    print(h.a + 1, h.a - 2)
    d = {"a": A("1.1.1.1"), "b": [A("2.2.2.2")]}
    print(d["a"], d["b"][0], d["a"] == 16843009, d["a"] == "1.1.1.1")
    print(A("1.2.3.4") < A("1.2.3.5"), A("1.2.3.4") <= A("1.2.3.4"), A("1.2.3.5") > A("1.2.3.4"))
    print(str(A(0)), str(A(4294967295)), str(A(b"\xff\x00\x01\x02")))
    for text in ["192.0.0.8", "192.0.0.9", "192.0.0.10", "192.0.0.170", "224.0.0.1",
                 "100.64.0.1", "240.0.0.1", "255.255.255.255"]:
        a = A(text)
        print("flags", text, a.is_private, a.is_global)
    print("hash", hash(A("1.1.1.1")) == hash(hex(16843009)),
          hash(A("1.1.1.1")) == hash(16843009))
    for bad in ["", "1.2.3", "1.2.3.4.5", "256.1.1.1", "01.2.3.4", "1..2.3", "1.2.3.x",
                "1234.1.1.1", "9999.1.1.1", "1.2.3.4444", "1.2.3.4/24", "1.2.3.4/", "/24"]:
        try:
            ipa.IPv4Address(bad)
            print("no error", bad)
        except ValueError as e:
            print("ValueError", e)
    for bad in [-1, 4294967296, b"\x01\x02\x03"]:
        try:
            ipa.IPv4Address(bad)
            print("no error", bad)
        except ValueError as e:
            print("ValueError", e)
    try:
        print(A("1.2.3.4") < 16909060)
    except TypeError as e:
        print("TypeError", e)


main()
"""

URLPARSE = r"""
import urllib.parse as up
from urllib.parse import parse_qs as pq, urlsplit as us


class Holder:
    def __init__(self, p):
        self.p = p


def groups(query: str) -> dict[str, list[str]]:
    return pq(query, keep_blank_values=True)


def main() -> None:
    for text in ["https://user:pa%20ss@EXAMPLE.com:8080/a/b?x=1#f", "http://[::1]:80/", "http://x",
                 "//host/path", "mailto:a@b", "  https://x/y?q=1#z\t", "HTTP://Example.COM/a;b?c#d"]:
        p = us(text)
        print(p.scheme, p.netloc, p.path, p.query, p.fragment, p.hostname, p.port, p.username, p.password,
              p.geturl(), repr(p), p[0], p[4], len(p), list(p))
    q = up.urlparse("HTTP://Example.COM/a;b?c#d")
    print(q.params, q.path, repr(q), q.geturl(), q[3])
    print(up.urlunsplit(("http", "h", "/p", "q=1", "f")))
    for query in ["a=1&b=2&a=3", "empty=&flag&x=%20hello%20world&x=a%2Bb", "a+b=c+d", "a", "a=",
                  "&&a=1&", "a=%zz&b=%41", "x=%C3%A9"]:
        for keep in [False, True]:
            print(repr(query), keep, up.parse_qsl(query, keep_blank_values=keep), groups(query))
        try:
            print(pq(query, strict_parsing=True))
        except ValueError as e:
            print("ValueError", e)
    h = Holder(us("https://Sub.Example.org:99/x?y=1"))
    print(h.p.hostname, h.p.port, h.p.path)
    xs = [us("https://a.example.com:1/x"), us("http://b.example.org:2/y?z=3")]
    print(xs[0].hostname, xs[1].port, xs[1].query)
    d = {"u": us("https://Dict.Example.com:7/p")}
    print(d["u"].hostname, d["u"].port)
    print(up.unquote("a%20b%2Bc"), up.unquote_plus("a+b%2Bc"))
    print(up.quote("a b/c?d=e&f", safe="/"), up.quote_plus("a b/c?d=e&f"), up.quote("héllo"))
    print(up.urlencode({"a": "1", "b": "x y&z"}), up.urlencode({"a": ["1", "2"]}, doseq=True))
    print(up.urlencode([("a", "1"), ("b", "2")]))
    print(up.urlencode([("a", ["1", "2"]), ("b", "3")], doseq=True))
    print(up.urlencode([("a", ("1", "2")), ("b", "3")], doseq=True))
    print(up.urlencode([("a", []), ("b", "3")], doseq=True))
    for text in ["http://x[::1]/", "http://[abc]/", "http://[]/", "http://[::1]x/",
                 "http://[1.2.3.4]/", "http://[v.x]/"]:
        try:
            print(us(text))
            print("no error", text)
        except ValueError as e:
            print("ValueError", e)
    print(up.urljoin("http://a/b/c/d;p?q", "../g"), up.urljoin("http://a/b/c/d;p?q", "//g/x"),
          up.urljoin("http://a/b/c/d;p?q", "?y"), up.urljoin("http://a/b/c/d;p?q", "#s"))
    for text in ["foo://h/a;b?q", "http://h/a;b/c", "http://h/a/b;c", "http://h/a;b;c/d",
                 "http://h/a;b?c;d#e;f"]:
        q = up.urlparse(text)
        print("params", text, q.path, repr(q.params), q.geturl())
    print("emptyhost", repr(us("http://:80/").hostname), repr(us("http://user@:99/x").hostname),
          repr(us("http://h:80/").hostname))
    print("strictempty", up.parse_qsl("", strict_parsing=True), up.parse_qs("", strict_parsing=True))
    try:
        print(up.parse_qsl("a=1&", strict_parsing=True))
    except ValueError as e:
        print("ValueError", e)
    print("enc", up.quote("é", encoding="latin-1"), up.unquote("%E9", encoding="latin-1"),
          up.unquote_plus("%E9", encoding="latin-1"), up.parse_qsl("x=%E9", encoding="latin-1"))
    print("enc2", up.quote("é", encoding="latin-1", errors="replace"),
          up.unquote("%E9", encoding="latin-1", errors="ignore"),
          up.urlencode({"x": "é"}, encoding="latin-1"))
    print("join", up.urljoin("x", ";x"), up.urljoin("x", ";x?y#s"),
          up.urljoin("http://a/b/c/d;p?q", ";x"))
    try:
        print(us("http://h:65536/"))
    except ValueError as e:
        print("ValueError", e)
    try:
        print(us("http://x:abc/"))
    except ValueError as e:
        print("ValueError", e)


main()
"""


def run_python(directory, source, name):
    path = Path(directory, name + '.py')
    path.write_text(source, encoding='utf-8')
    built = subprocess.run([sys.executable, path.name], cwd=directory, capture_output=True, text=True, timeout=300)
    return built


def run_ail(directory, source, name, unified):
    path = Path(directory, name + '.ail')
    path.write_text(source, encoding='utf-8')
    exe = Path(directory, name + ('_g' if unified else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    if unified:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    built = subprocess.run([sys.executable, str(ROOT / 'ail_chatgpt.py'), 'compile', path.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory, capture_output=True,
                           text=True, timeout=900, env=env)
    if built.returncode != 0:
        return built, None
    ran = subprocess.run([str(exe)], cwd=directory, capture_output=True, text=True, timeout=300)
    return built, ran


class Stdlib6Test(unittest.TestCase):
    def compile_both(self, source, name):
        with tempfile.TemporaryDirectory(prefix='ail-stdlib6-') as tmp:
            oracle = run_python(tmp, source, name)
            self.assertEqual(oracle.returncode, 0, oracle.stderr)
            for unified in (False, True):
                built, ran = run_ail(tmp, source, name, unified)
                self.assertEqual(built.returncode, 0, built.stderr)
                self.assertEqual(ran.returncode, oracle.returncode, ran.stderr)
                self.assertEqual(ran.stdout, oracle.stdout, ran.stderr)

    def test_ipaddress_ipv4(self):
        self.compile_both(IPADDRESS, 'probe_ipaddress')

    def test_urllib_parse(self):
        self.compile_both(URLPARSE, 'probe_urlparse')

    def test_preludes_run_under_cpython(self):
        ip = load_prelude('ipaddress')
        a = ip._AilIPv4Address('192.168.1.10')
        self.assertEqual((str(a), int(a), a.packed, a.is_private), ('192.168.1.10', 3232235786,
                                                                   b'\xc0\xa8\x01\n', True))
        self.assertEqual(str(ip._AilIPv4Address(16909060)), '1.2.3.4')
        with self.assertRaises(ValueError) as raised:
            ip._AilIPv4Address('1234.1.1.1')
        self.assertEqual(str(raised.exception),
                         "At most 3 characters permitted in '1234' in '1234.1.1.1'")
        up = load_prelude('urlparse')
        p = up._AilUrlSplit('https://User:pa%20ss@Example.COM:8443/a/b?x=1#f')
        self.assertEqual((p.scheme, p.hostname, p.port, p.username, p.password, p.path, p.query, p.fragment),
                         ('https', 'example.com', 8443, 'User', 'pa%20ss', '/a/b', 'x=1', 'f'))
        self.assertEqual(up._AilParseQs('a=1&a=2&b=', keep_blank_values=True),
                         {'a': ['1', '2'], 'b': ['']})
        self.assertEqual((up._AilUrlParse('foo://h/a;b?q').params,
                          up._AilUrlParse('http://h/a;b/c').params), ('', ''))
        self.assertEqual(up._AilUrlParse('http://h/a/b;c').params, 'c')
        self.assertIsNone(up._AilUrlSplit('http://:80/').hostname)
        self.assertEqual(up._AilParseQsl('', strict_parsing=True), [])
        self.assertEqual(up._AilParseQs('', strict_parsing=True), {})
        self.assertEqual(up._ail_up_quote('é', '/', False, 'latin-1', None), '%E9')
        self.assertEqual(up._ail_up_unquote('%E9', False, 'latin-1', 'replace'), 'é')
        self.assertEqual(up._AilParseQsl('x=%E9', encoding='latin-1'), [('x', 'é')])
        self.assertEqual(up._AilUrlJoin('x', ';x'), '/;x')
        self.assertEqual(up._AilUrlJoin('x', ';x?y#s'), '/;x?y#s')
        self.assertEqual(up._AilUrlEncode([('a', ['1', '2']), ('b', '3')], doseq=True),
                         'a=1&a=2&b=3')
        self.assertEqual(up._AilUrlEncode([('a', ('1', '2')), ('b', '3')], doseq=True),
                         'a=1&a=2&b=3')
        self.assertEqual(up._AilUrlEncode([('a', []), ('b', '3')], doseq=True), 'b=3')
        for text, message in [('http://x[::1]/', 'Invalid IPv6 URL'),
                              ('http://[abc]/', "'abc' does not appear to be an IPv4 or IPv6 address"),
                              ('http://[::1]x/', 'Invalid IPv6 URL'),
                              ('http://[1.2.3.4]/', 'An IPv4 address cannot be in brackets'),
                              ('http://[v.x]/', 'IPvFuture address is invalid')]:
            with self.assertRaises(ValueError) as raised:
                up._AilUrlSplit(text)
            self.assertEqual(str(raised.exception), message)
        self.assertEqual((ip._AilIPv4Address('192.0.0.8').is_private,
                          ip._AilIPv4Address('192.0.0.8').is_global), (True, False))
        self.assertEqual((ip._AilIPv4Address('224.0.0.1').is_private,
                          ip._AilIPv4Address('224.0.0.1').is_global), (False, True))
        self.assertFalse(ip._AilIPv4Address('192.0.0.9').is_private)
        self.assertTrue(ip._AilIPv4Address('192.0.0.10').is_global)
        with self.assertRaises(ValueError) as raised:
            ip._AilIPv4Address('1.2.3.4/24')
        self.assertEqual(str(raised.exception), "Unexpected '/' in '1.2.3.4/24'")
        self.assertFalse(hash(ip._AilIPv4Address('1.1.1.1')) == hash(16843009))
        self.assertEqual(hash(ip._AilIPv4Address('1.1.1.1')), hash(hex(16843009)))

    def test_unsupported_names_are_refused(self):
        for source, needle in [
            ('import ipaddress\n\ndef main() -> None:\n    print(ipaddress.IPv6Address("::1"))\n\nmain()\n',
             'ipaddress.IPv6Address is not built'),
            ('from urllib.parse import urldefrag\n\ndef main() -> None:\n    print(urldefrag("x#y"))\n\nmain()\n',
             'urllib.parse.urldefrag is not built'),
        ]:
            with tempfile.TemporaryDirectory(prefix='ail-stdlib6-') as tmp:
                path = Path(tmp, 'bad.ail')
                path.write_text(source, encoding='utf-8')
                built = subprocess.run([sys.executable, str(ROOT / 'ail_chatgpt.py'), 'compile', path.name,
                                        '--syntax', 'python', '-o', 'bad'], cwd=tmp, capture_output=True,
                                       text=True, timeout=900, env=dict(os.environ, AIL_NO_CACHE='1'))
                self.assertNotEqual(built.returncode, 0)
                self.assertIn(needle, built.stderr)


if __name__ == '__main__':
    unittest.main()
