"""G12: `urllib.request` / `urllib.error` / `urllib.parse` over libcurl, compared with CPython 3.12.

Every program below is ordinary Python. CPython 3.12 runs it as the oracle, the compiled program runs against
the SAME local server, and the two must print the same bytes -- or the spelling is refused by name at compile
time ("write instead:"). Nothing here contacts the internet: the servers listen on 127.0.0.1 only, the proxy
variables are cleared on both sides, and a name is never resolved except "localhost".

* the server (http.server, threaded) echoes the method, target, every request header (sorted by name: libcurl puts Host first) and
  the body as JSON, answers any status, redirects (301/302/303/307/308, absolute / relative / odd Locations,
  chains, loops), chunked and close-delimited bodies, large and binary bodies, duplicate and oddly spelt
  headers, gzip bytes that must NOT be decoded, and slow responses;
* a raw socket server records the exact bytes of the request head and body each client sends (header order and
  spelling included) for many Request shapes, so the wire format is compared byte for byte;
* HTTPS tests run when the openssl command line tool is present: a throw-away CA, a server certificate for
  127.0.0.1 / localhost signed by it, an untrusted self-signed one and one for another name, with SSL_CERT_FILE
  naming the CA on both sides; otherwise they are skipped with that reason;
* urllib.parse functions are compared on corpora of awkward strings;
* refusals by name, the missing-libcurl message (AIL_NO_CURL=1), the C of programs that do not use urllib
  (nothing of it), and urllib.parse alone not linking libcurl.

The whole module is skipped, with a reason, where libcurl's header is not installed (the public CI images on
other platforms) or CPython is not 3.12 (the User-Agent and the wire format are those of 3.12).
Typed programs are built with AIL_NO_GENERAL=1 and AIL_IR=0 and 1.
"""
import base64
import gzip
import http.server
import json
import os
import random
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")
PKG = str(ROOT / "python" / "pkg-v12")
OPENSSL = shutil.which("openssl")

SERVER = None
RAW = None
TLS = None


def setUpModule():
    if sys.version_info[:2] != (3, 12):
        raise unittest.SkipTest("CPython 3.12 is the oracle (its User-Agent and wire format are 3.12's); this is %d.%d" % sys.version_info[:2])
    if os.name != "posix":
        raise unittest.SkipTest("urllib.request is built and tested on POSIX hosts (libcurl on Windows comes with the G6 runner)")
    sys.path.insert(0, PKG)
    try:
        import urllower
        found = urllower.available()
    finally:
        sys.path.remove(PKG)
    if not found:
        raise unittest.SkipTest("libcurl's header (curl/curl.h) is not installed: apt install libcurl4-openssl-dev / "
                                "brew install curl / pacman -S mingw-w64-ucrt-x86_64-curl")
    global SERVER, RAW
    SERVER = Server()
    RAW = RawServer()


def tearDownModule():
    for each in (SERVER, RAW, TLS):
        if each is not None:
            each.close()


# ---------------------------------------------------------------------------------------- the servers

def pattern(n):
    out = bytearray()
    x = 12345
    while len(out) < n:
        x = (x * 1103515245 + 12345) % 2147483648
        out.append((x >> 16) & 255)
    return bytes(out[:n])


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "AILTest"
    sys_version = ""

    def log_message(self, *args):
        pass

    def body_in(self):
        if self.headers.get("Transfer-Encoding", "").lower() == "chunked":
            out = b""
            while True:
                size = int(self.rfile.readline().split(b";")[0], 16)
                if size == 0:
                    self.rfile.readline()
                    return out
                out += self.rfile.read(size)
                self.rfile.readline()
        return self.rfile.read(int(self.headers.get("Content-Length") or 0))

    def reply(self, code, body=b"", headers=(), length=True, reason=None):
        self.send_response(code, reason)
        for key, value in headers:
            self.send_header(key, value)
        if length:
            self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        if self.command != "HEAD" and code not in (204, 304) and body:
            self.wfile.write(body)
        self.close_connection = True

    def handle_any(self):
        data = self.body_in()
        parts = urllib.parse.urlsplit(self.path)
        query = urllib.parse.parse_qs(parts.query)
        path = parts.path
        if path.startswith("/echo"):
            text = data.decode("latin-1") if len(data) < 4096 else "<%d bytes, sum %d>" % (len(data), sum(data))
            doc = {"method": self.command, "target": self.path, "headers": sorted((list(h) for h in self.headers.items()), key=lambda h: h[0].lower()),
                   "body_len": len(data), "body": text}
            return self.reply(200, json.dumps(doc).encode("ascii"), [("Content-Type", "application/json")])
        if path.startswith("/status/"):
            code = int(path.split("/")[2])
            headers = [("Content-Type", "text/plain")]
            if "location" in query:
                headers.append(("Location", query["location"][0]))
            return self.reply(code, ("status %d\n" % code).encode(), headers)
        if path == "/redir":
            if "code" not in query:
                return self.reply(200, ("redir without parameters: " + parts.query + "\n").encode(), [("Content-Type", "text/plain")])
            code = int(query["code"][0])
            return self.reply(code, b"moved\n", [("Content-Type", "text/plain"), ("Location", query.get("to", [""])[0]),
                                                 ("X-Hop", "redir")])
        if path.startswith("/hops/"):
            left = int(path.split("/")[2])
            code = int(query.get("code", ["302"])[0])
            if left == 0:
                return self.reply(200, b"done\n", [("Content-Type", "text/plain")])
            return self.reply(code, b"", [("Location", "/hops/%d?code=%d" % (left - 1, code))])
        if path == "/loop":
            return self.reply(302, b"", [("Location", "/loop")])
        if path == "/chunked":
            parts_n, size = int(query.get("parts", ["4"])[0]), int(query.get("size", ["10"])[0])
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Transfer-Encoding", "chunked")
            self.send_header("Connection", "close")
            self.end_headers()
            for i in range(parts_n):
                chunk = (chr(97 + i % 26) * size).encode()
                self.wfile.write(b"%x\r\n%s\r\n" % (len(chunk), chunk))
                self.wfile.flush()
                time.sleep(0.002)
            self.wfile.write(b"0\r\n\r\n")
            self.close_connection = True
            return None
        if path == "/large":
            n = int(query["n"][0])
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(n))
            self.send_header("Connection", "close")
            self.end_headers()
            block = pattern(65536)
            left = n
            while left > 0:
                piece = block[:min(left, len(block))]
                self.wfile.write(piece)
                left -= len(piece)
            self.close_connection = True
            return None
        if path == "/binary":
            return self.reply(200, bytes(range(256)) * 4, [("Content-Type", "application/octet-stream")])
        if path == "/empty":
            return self.reply(200, b"", [("Content-Type", "text/plain")])
        if path == "/close":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(b"read until the socket closes\n" * 50)
            self.close_connection = True
            return None
        if path == "/gzip":
            return self.reply(200, gzip.compress(b"hello gzip " * 40, mtime=0),
                              [("Content-Type", "text/plain"), ("Content-Encoding", "gzip")])
        if path == "/multi":
            return self.reply(200, b"multi\n", [("Content-Type", "text/plain"), ("X-Multi", "first"), ("x-multi", "second"),
                                                ("Set-Cookie", "a=1"), ("Set-Cookie", "b=2"), ("x-lower", "low"),
                                                ("X-Space", "   padded   "), ("X-Empty", ""), ("X-Colon", "a:b:c")])
        if path == "/slow":
            time.sleep(float(query["s"][0]))
            return self.reply(200, b"slow\n", [("Content-Type", "text/plain")])
        if path == "/utf8":
            return self.reply(200, "héllo wörld ✓ 日本語\n".encode("utf-8"), [("Content-Type", "text/plain; charset=utf-8")])
        if path == "/truncated":
            self.send_response(200)
            self.send_header("Content-Length", "1000")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(b"only part")
            self.close_connection = True
            return None
        if path == "/reason":
            return self.reply(200, b"x", [], reason="Custom Reason Text")
        if path == "/noreason":
            self.wfile.write(b"HTTP/1.1 200\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok")
            self.close_connection = True
            return None
        return self.reply(404, b"not found: " + path.encode() + b"\n", [("Content-Type", "text/plain")])

    do_GET = do_POST = do_PUT = do_DELETE = do_PATCH = do_HEAD = do_OPTIONS = handle_any


class QuietServer(http.server.ThreadingHTTPServer):
    def handle_error(self, request, client_address):      # a client that hangs up early is not news
        pass


class Server:
    """The http.server on 127.0.0.1, optionally behind TLS."""

    def __init__(self, certfile=None, keyfile=None):
        self.httpd = QuietServer(("127.0.0.1", 0), Handler)
        self.httpd.daemon_threads = True
        self.scheme = "http"
        if certfile:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(certfile, keyfile)
            self.httpd.socket = context.wrap_socket(self.httpd.socket, server_side=True)
            self.scheme = "https"
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    @property
    def base(self):
        return "%s://127.0.0.1:%d" % (self.scheme, self.port)

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


class RawServer:
    """Records the bytes of each request head and body, answers 200 `ok`."""

    def __init__(self):
        self.sock = socket.socket()
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(16)
        self.port = self.sock.getsockname()[1]
        self.seen = []
        self.lock = threading.Lock()
        self.stop = False
        self.thread = threading.Thread(target=self.loop, daemon=True)
        self.thread.start()

    @property
    def base(self):
        return "http://127.0.0.1:%d" % self.port

    def loop(self):
        while not self.stop:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            threading.Thread(target=self.serve, args=(conn,), daemon=True).start()

    def serve(self, conn):
        conn.settimeout(10)
        data = b""
        try:
            while b"\r\n\r\n" not in data:
                chunk = conn.recv(65536)
                if not chunk:
                    break
                data += chunk
            head, _, rest = data.partition(b"\r\n\r\n")
            length = 0
            for line in head.split(b"\r\n")[1:]:
                if line.lower().startswith(b"content-length:"):
                    length = int(line.split(b":")[1])
            expect = b"expect: 100-continue" in head.lower()
            if expect:
                conn.sendall(b"HTTP/1.1 100 Continue\r\n\r\n")
            while len(rest) < length:
                chunk = conn.recv(65536)
                if not chunk:
                    break
                rest += chunk
            with self.lock:
                self.seen.append(head + b"\r\n\r\n" + rest)
            conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nContent-Type: text/plain\r\nConnection: close\r\n\r\nok")
        except OSError:
            pass
        finally:
            conn.close()

    def take(self):
        with self.lock:
            out, self.seen = self.seen, []
        return out

    def close(self):
        self.stop = True
        try:
            self.sock.close()
        except OSError:
            pass


def hostless(raw):
    """(request bytes without the Host line, the Host line): libcurl always writes Host right after the request
    line where http.client writes it after Accept-Encoding -- the one difference in the head (DIFFERENCES C25)."""
    head, sep, body = raw.partition(b"\r\n\r\n")
    head = head.replace(b": \r\n", b":\r\n")        # a header with an empty value: libcurl writes "Name:" where http.client writes "Name: "
    lines = head.split(b"\r\n")
    host = [line for line in lines if line.lower().startswith(b"host:")]
    kept = [line for line in lines if not line.lower().startswith(b"host:")]
    return b"\r\n".join(kept) + sep + body, host


def free_port():
    """A port nothing listens on (bound and released)."""
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


# ---------------------------------------------------------------------------------------- running programs

PROXY_VARS = ("http_proxy", "https_proxy", "all_proxy", "ftp_proxy", "no_proxy", "REQUEST_METHOD")


def program_env(**extra):
    env = dict(os.environ, PYTHONUTF8="1", LC_ALL="C.UTF-8")
    env.pop("PYTHONPATH", None)
    env.pop("AIL_NO_CURL", None)
    for name in PROXY_VARS:
        env.pop(name, None)
        env.pop(name.upper(), None)
    env["no_proxy"] = "127.0.0.1,localhost"
    env.update(extra)
    return env


def build(src, exe, ir, extra_env=None, extra=()):
    env = dict(os.environ, AIL_IR=ir, AIL_NO_GENERAL="1")
    env.pop("AIL_TARGET", None)
    env.update(extra_env or {})
    return subprocess.run([sys.executable, "-B", CLI, "compile", str(src), "-o", str(exe), *extra],
                          capture_output=True, text=True, timeout=900, env=env)


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ail-http-")
        cls.dir = Path(cls.temp.name)
        cls.exe = {}

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def program(self, name, text, irs=("0", "1")):
        """(source path, {ir: executable}) of a program, compiled once."""
        if name not in self.exe:
            src = self.dir / (name + ".py")
            src.write_text(text, encoding="utf-8")
            built = {}
            for ir in irs:
                exe = self.dir / ("%s.ir%s" % (name, ir))
                done = build(src, exe, ir)
                self.assertEqual(done.returncode, 0, "AIL_IR=%s: %s" % (ir, (done.stderr or done.stdout)[-3000:]))
                self.assertNotIn("general path", done.stderr)
                built[ir] = exe
            self.exe[name] = (src, built)
        return self.exe[name]

    def compare(self, name, text, stdin, env=None, irs=("0", "1"), timeout=120, show=2400):
        """CPython's stdout for the program equals each build's, on the same stdin."""
        src, built = self.program(name, text, irs)
        env = program_env(**(env or {}))
        want = subprocess.run([sys.executable, str(src)], input=stdin.encode(), capture_output=True, timeout=timeout, env=env)
        self.assertEqual(want.returncode, 0, want.stderr.decode()[-2000:])
        for ir, exe in built.items():
            got = subprocess.run([str(exe)], input=stdin.encode(), capture_output=True, timeout=timeout, env=env)
            self.assertEqual(got.returncode, 0, "AIL_IR=%s: %s" % (ir, got.stderr.decode()[-2000:]))
            if got.stdout != want.stdout:
                a = want.stdout.decode("utf-8", "replace").split("\n")
                b = got.stdout.decode("utf-8", "replace").split("\n")
                for i in range(max(len(a), len(b))):
                    x = a[i] if i < len(a) else "<none>"
                    y = b[i] if i < len(b) else "<none>"
                    if x != y:
                        self.fail("AIL_IR=%s line %d: CPython %r, AIL %r\n--- CPython\n%s\n--- AIL\n%s"
                                  % (ir, i + 1, x[:400], y[:400], "\n".join(a[max(0, i - 6):i + 3])[:show],
                                     "\n".join(b[max(0, i - 6):i + 3])[:show]))
        return want.stdout.decode("utf-8", "replace")

    def refused(self, text, *needles, extra_env=None):
        src = self.dir / ("refused%d.py" % abs(hash(text)))
        src.write_text(text, encoding="utf-8")
        exe = self.dir / "refused.exe"
        if exe.exists():
            exe.unlink()
        done = build(src, exe, "1", extra_env=extra_env)
        self.assertNotEqual(done.returncode, 0, done.stdout)
        self.assertFalse(exe.exists())
        self.assertNotIn("Traceback", done.stderr)
        for needle in needles:
            self.assertIn(needle, done.stderr)
        return done.stderr


# ---------------------------------------------------------------------------------------- programs

FETCH = r'''import sys
import urllib.request
import urllib.error


def checksum(data: bytes) -> int:
    h = 7
    for b in data:
        h = (h * 31 + b) % 1000003
    return h


def fetch(base: str, path: str) -> None:
    print("==", path)
    try:
        with urllib.request.urlopen(base + path, timeout=30) as r:
            body = r.read()
            print("status", r.status, r.reason, r.getcode())
            print("url", r.geturl().replace(base, "BASE"), r.url.replace(base, "BASE"))
            print("type", r.headers.get("Content-Type", "-"), "|", r.getheader("X-Multi", "-"), "|", r.headers.get("x-lower", "-"))
            print("more", r.headers.get("X-Space", "-"), "|", r.headers.get("X-Empty", "-"), "|", r.getheader("x-colon", "-"), "|", r.headers.get("Content-Encoding", "-"))
            print("has", "Content-Type" in r.headers, "x-nope" in r.headers, "CONTENT-TYPE" in r.headers)
            print("len", len(body), checksum(body), r.headers.get("Content-Length", "-"), r.headers.get("Transfer-Encoding", "-"))
            ctype = r.headers.get("Content-Type", "")
            if len(body) < 6000 and (ctype.startswith("text/") or ctype.startswith("application/json")) and r.headers.get("Content-Encoding", "") == "":
                print(body.decode())
    except urllib.error.HTTPError as e:
        print("HTTPError", e.code, e.reason, e.url.replace(base, "BASE"), e.msg, e.getcode(), e.status)
        print("str", e)
        print("hdr", e.headers.get("Content-Type", "-"), "|", e.headers.get("Location", "-").replace(base, "BASE"), "|", e.headers.get("X-Hop", "-"))
        body = e.read()
        print("len", len(body), body.decode())
        print("again", len(e.read()))
    except urllib.error.URLError as e:
        print("URLError", e.reason)
        print("str", e)


def main() -> int:
    lines = sys.stdin.read().split("\n")
    base = lines[0]
    for line in lines[1:]:
        if line != "":
            fetch(base, line)
    return 0


sys.exit(main())
'''

REQUESTS = r'''import sys
import urllib.request
import urllib.error


def show(r: urllib.request.Request, base: str) -> None:
    print("method", r.get_method(), "|", r.full_url.replace(base, "BASE"), "|", r.get_full_url().replace(base, "BASE"))
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            print("status", resp.status, resp.reason)
            print(resp.read().decode())
    except urllib.error.HTTPError as e:
        print("HTTPError", e.code, e.reason)
        print(e.read().decode())


def main() -> int:
    lines = sys.stdin.read().split("\n")
    base = lines[0]
    kind = int(lines[1])
    url = base + "/echo?k=" + str(kind)
    if kind == 0:
        show(urllib.request.Request(url), base)
    elif kind == 1:
        show(urllib.request.Request(url, data=b"a=1&b=2"), base)
    elif kind == 2:
        show(urllib.request.Request(url, data=b'{"x": 1}', headers={"Content-Type": "application/json", "X-Token": "abc"}), base)
    elif kind == 3:
        show(urllib.request.Request(url, method="PUT"), base)
    elif kind == 4:
        show(urllib.request.Request(url, data=b"payload", method="PUT"), base)
    elif kind == 5:
        show(urllib.request.Request(url, method="DELETE"), base)
    elif kind == 6:
        show(urllib.request.Request(url, method="HEAD"), base)
    elif kind == 7:
        show(urllib.request.Request(url, data=b"", method="PATCH"), base)
    elif kind == 8:
        show(urllib.request.Request(url, headers={"x-custom-HEADER": "v", "ACCEPT-language": "en", "accept": "text/html"}), base)
    elif kind == 9:
        show(urllib.request.Request(url, headers={"User-Agent": "mine/1.0", "Accept-Encoding": "gzip", "X-Trace-Id": "k"}), base)
    elif kind == 10:
        h: dict[str, str] = {"X-One": "1", "X-Two": "2"}
        show(urllib.request.Request(url, headers=h, data=b"zz"), base)
    elif kind == 11:
        req = urllib.request.Request(url)
        req.add_header("X-Added", "yes")
        req.add_header("x-added", "again")
        req.add_unredirected_header("X-Unredirected", "u")
        print(req.has_header("X-added"), req.has_header("x-added"), req.get_header("X-added", "none"), req.get_header("Nope", "none"))
        req.remove_header("X-added")
        print(req.has_header("X-added"))
        show(req, base)
    elif kind == 12:
        show(urllib.request.Request(url, headers={"Host": "example.test"}), base)
    elif kind == 13:
        show(urllib.request.Request(url, headers={"Connection": "keep-alive", "X-Z": "z"}), base)
    elif kind == 14:
        show(urllib.request.Request(url, data=b""), base)
    elif kind == 15:
        show(urllib.request.Request(url, data=b"abc", method="GET"), base)
    elif kind == 16:
        show(urllib.request.Request(url, method="OPTIONS"), base)
    elif kind == 17:
        show(urllib.request.Request(url + "#frag"), base)
    elif kind == 18:
        show(urllib.request.Request(url, data=b"x" * 1500000), base)
    elif kind == 19:
        show(urllib.request.Request(url, data=b"k=v", headers={"Content-Type": "text/plain", "Content-Length": "3"}), base)
    elif kind == 20:
        show(urllib.request.Request("  <URL:" + url + ">  "), base)
    elif kind == 21:
        show(urllib.request.Request(url, method="get"), base)
    return 0


sys.exit(main())
'''

URLOPEN_SHAPES = r'''import sys
import urllib.request
from urllib.request import urlopen, Request
from urllib import request as ur


def main() -> int:
    lines = sys.stdin.read().split("\n")
    base = lines[0]
    url = base + "/echo"
    r1 = urlopen(url)
    print(r1.status, r1.read().decode()[:40])
    r1.close()
    print(r1.read() == b"")
    r2 = ur.urlopen(url, data=b"abc", timeout=5)
    print(r2.status, r2.read(30).decode(), "|", r2.read(10).decode(), "|", len(r2.read()), len(r2.read()))
    r3 = urllib.request.urlopen(url, b"post body", 5.5)
    print(r3.getcode(), len(r3.read()))
    req = Request(url + "?q=1", data=b"zz")
    print(urlopen(req).read().decode().split(",")[0])
    print(urlopen(Request(url)).status, urlopen(url, timeout=None).status)
    print(urlopen(url).read().decode()[:10])
    text = urlopen(url + "?utf").read().decode()
    print(len(text))
    return 0


sys.exit(main())
'''

PARSE = r'''import sys
import urllib.parse
from urllib.parse import quote, quote_plus, unquote, unquote_plus, urlencode, urljoin


def main() -> int:
    for line in sys.stdin.read().split("\n"):
        if line.startswith("q "):
            s = line[2:]
            print("q", quote(s), quote(s, safe=""), quote(s, "/:"), quote_plus(s), quote_plus(s, safe="/"), urllib.parse.quote(s, safe="~"))
        elif line.startswith("u "):
            s = line[2:]
            print("u", unquote(s), "|", unquote_plus(s), "|", urllib.parse.unquote(s).encode().hex())
        elif line.startswith("j "):
            parts = line[2:].split("\t")
            print("j", urljoin(parts[0], parts[1]), "|", urllib.parse.urljoin(parts[0], parts[1]))
        elif line.startswith("e "):
            parts = line[2:].split("\t")
            d: dict[str, str] = {parts[0]: parts[1], parts[2]: parts[3]}
            print("e", urlencode(d), "|", urlencode({"a": "1 2", "b&c": "d=e", "n": 5, "f": 1.5, "t": True}), "|", urlencode({"k": parts[0]}))
    return 0


sys.exit(main())
'''

RAWREQ = r'''import sys
import urllib.request
import urllib.error


def make(base: str, kind: int) -> urllib.request.Request:
    url = base + "/raw/path?a=1&b=2"
    if kind == 0:
        return urllib.request.Request(url)
    if kind == 1:
        return urllib.request.Request(url, data=b"a=1&b=2")
    if kind == 2:
        return urllib.request.Request(url, data=b'{"x": 1}', headers={"Content-Type": "application/json", "X-Token": "abc"})
    if kind == 3:
        return urllib.request.Request(url, method="PUT")
    if kind == 4:
        return urllib.request.Request(url, data=b"payload", method="PUT")
    if kind == 5:
        return urllib.request.Request(url, method="DELETE")
    if kind == 6:
        return urllib.request.Request(url, method="HEAD")
    if kind == 7:
        return urllib.request.Request(url, data=b"", method="PATCH")
    if kind == 8:
        return urllib.request.Request(url, headers={"x-custom-HEADER": "v", "ACCEPT-language": "en", "accept": "text/html"})
    if kind == 9:
        return urllib.request.Request(url, headers={"User-Agent": "mine/1.0", "Accept-Encoding": "gzip", "X-Trace-Id": "k"})
    if kind == 10:
        return urllib.request.Request(url, headers={"Host": "example.test", "X-A": "1"})
    if kind == 11:
        return urllib.request.Request(url, headers={"Connection": "keep-alive", "X-Z": "z"})
    if kind == 12:
        return urllib.request.Request(url, data=b"")
    if kind == 13:
        return urllib.request.Request(url, data=b"abc", method="GET")
    if kind == 14:
        return urllib.request.Request(url, method="OPTIONS")
    if kind == 15:
        return urllib.request.Request(url, data=b"x" * 1500000)
    if kind == 16:
        return urllib.request.Request(url, data=b"k=v", headers={"Content-Type": "text/plain", "Content-Length": "3"})
    if kind == 17:
        return urllib.request.Request(base + "/a%20b/c?x=%7E#frag")
    if kind == 18:
        return urllib.request.Request(base.replace("127.0.0.1", "localhost") + "/")
    if kind == 19:
        return urllib.request.Request(base + "?only=query")
    if kind == 20:
        return urllib.request.Request(base)
    if kind == 21:
        return urllib.request.Request(url, data=b"d", headers={"content-type": "x/y", "ACCEPT": "*/*", "x-b": "1", "x-a": "2"})
    return urllib.request.Request(url, headers={"Transfer-Encoding": "gzip", "X-Q": ""})


def main() -> int:
    lines = sys.stdin.read().split("\n")
    base = lines[0]
    kind = int(lines[1])
    r = make(base, kind)
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            print(resp.status, resp.read().decode())
    except urllib.error.URLError as e:
        print("URLError", e.reason)
    return 0


sys.exit(main())
'''

ERRORS = r'''import sys
import urllib.request
import urllib.error


def attempt(base: str, url: str) -> None:
    print("==", url.replace(base, "BASE"))
    try:
        r = urllib.request.urlopen(url, timeout=30)
        print("ok", r.status)
    except urllib.error.HTTPError as e:
        print("HTTPError", e.code, e.reason, "|", e)
    except urllib.error.URLError as e:
        print("URLError", e.reason, "|", e)
    except ValueError as e:
        print("ValueError")


def attempt_os(url: str) -> None:
    try:
        r = urllib.request.urlopen(url, timeout=30)
        print("ok", r.status)
    except OSError:
        print("OSError")


def attempt_url_first(url: str) -> None:
    try:
        urllib.request.urlopen(url, timeout=30)
        print("ok")
    except urllib.error.URLError:
        print("URLError handler")
    except OSError:
        print("OSError handler")


def attempt_tuple(url: str) -> None:
    try:
        urllib.request.urlopen(url, timeout=30)
        print("ok")
    except (urllib.error.HTTPError, ValueError):
        print("tuple handler")
    except urllib.error.URLError:
        print("URLError handler")


def main() -> int:
    lines = sys.stdin.read().split("\n")
    base = lines[0]
    dead = lines[1]
    for line in lines[2:]:
        if line != "":
            attempt(base, base + line)
    attempt(base, dead)
    attempt(base, "not a url")
    attempt(base, "gopher://127.0.0.1/x")
    attempt(base, "http:///nohost")
    attempt(base, "localhost:80/x")
    attempt(base, base.upper() + "/status/404")
    attempt(base, " " + base + "/echo ")
    attempt(base, "<URL:" + base + "/echo>")
    attempt(base, base + "/ecého")
    attempt_os(base + "/status/404")
    attempt_os(dead)
    attempt_os(base + "/status/200")
    attempt_url_first(base + "/status/500")
    attempt_url_first(dead)
    attempt_tuple(base + "/status/403")
    attempt_tuple(dead)
    attempt_tuple(base + "/status/200")
    return 0


sys.exit(main())
'''

TIMEOUT = r'''import sys
import urllib.request
import urllib.error


def main() -> int:
    lines = sys.stdin.read().split("\n")
    base = lines[0]
    try:
        urllib.request.urlopen(base + "/slow?s=3", timeout=1)
        print("no timeout")
    except OSError:
        print("timed out")
    r = urllib.request.urlopen(base + "/slow?s=0.2", timeout=5)
    print(r.status, r.read().decode().strip())
    t = 2
    r = urllib.request.urlopen(base + "/slow?s=0.1", timeout=t)
    print(r.status)
    return 0


sys.exit(main())
'''

SCOPES = r'''import sys
import urllib.request
import urllib.error


class Fetcher:
    def __init__(self, base: str):
        self.base = base
        self.count = 0

    def get(self, path: str) -> str:
        with urllib.request.urlopen(self.base + path) as r:
            self.count += 1
            return r.read().decode()

    def code(self, path: str) -> int:
        try:
            urllib.request.urlopen(self.base + path)
            return 200
        except urllib.error.HTTPError as e:
            return e.code


def fetch_len(url: str) -> int:
    r = urllib.request.urlopen(url)
    n = len(r.read())
    r.close()
    return n


def build(url: str, extra: str) -> urllib.request.Request:
    return urllib.request.Request(url, headers={"X-Extra": extra})


def run(req: urllib.request.Request) -> str:
    with urllib.request.urlopen(req) as r:
        return r.read().decode()


def retry(url: str) -> int:
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url) as r:
                return r.status
        except urllib.error.HTTPError as e:
            if e.code < 500:
                return e.code
    return -1


def main() -> int:
    lines = sys.stdin.read().split("\n")
    base = lines[0]
    f = Fetcher(base)
    print(len(f.get("/echo")), f.count, f.code("/status/404"), f.code("/echo"))
    print(fetch_len(base + "/large?n=100000"), fetch_len(base + "/empty"))
    print(run(build(base + "/echo", "ex")).count("X-Extra"))
    print(retry(base + "/status/418"), retry(base + "/status/200"), retry(base + "/status/503"))
    total = 0
    for i in range(5):
        with urllib.request.urlopen(base + "/chunked?parts=3&size=7") as r:
            total += len(r.read())
    print(total)
    return 0


sys.exit(main())
'''


def lines_of(base, *rest):
    return "\n".join([base, *rest]) + "\n"


def redir(code, to):
    return "/redir?code=%d&to=%s" % (code, urllib.parse.quote(to, safe=""))


# ---------------------------------------------------------------------------------------- the tests

class GetTests(Base):
    def test_status_headers_and_bodies(self):
        paths = ["/echo", "/echo?x=1&y=two%20words", "/status/200", "/status/201", "/status/202", "/status/204", "/status/206",
                 "/utf8", "/multi", "/empty", "/binary", "/reason", "/noreason", "/gzip", "/close", "/chunked",
                 "/chunked?parts=40&size=3000", "/large?n=0", "/large?n=1", "/large?n=70000", "/large?n=3000001"]
        out = self.compare("fetch", FETCH, lines_of(SERVER.base, *paths))
        self.assertIn("status 200 OK 200", out)
        self.assertIn("len 3000001", out)

    def test_error_statuses(self):
        paths = ["/status/%d" % c for c in (300, 304, 305, 400, 401, 403, 404, 405, 410, 418, 429, 500, 501, 502, 503, 504, 599)]
        paths += ["/status/301", "/status/302", "/status/303", "/status/307", "/status/308",
                  "/status/302?location=%2Fecho", "/missing/page"]
        out = self.compare("fetch", FETCH, lines_of(SERVER.base, *paths))
        self.assertIn("HTTPError 404 Not Found", out)

    def test_connection_refused(self):
        base = "http://127.0.0.1:%d" % free_port()
        out = self.compare("fetch", FETCH, lines_of(base, "/echo"))
        self.assertIn("Connection refused", out)

    def test_urlopen_spellings(self):
        out = self.compare("shapes", URLOPEN_SHAPES, lines_of(SERVER.base))
        self.assertIn("True", out)

    def test_scopes_classes_and_loops(self):
        self.compare("scopes", SCOPES, lines_of(SERVER.base))

    def test_truncated_body_is_an_error(self):
        # CPython raises http.client.IncompleteRead when the body is read; the build reports a URLError at urlopen
        # (DIFFERENCES C27): either way no body is returned
        prog = ("import sys\nimport urllib.request\n\ndef main() -> int:\n    base = sys.stdin.read().strip()\n"
                "    try:\n        r = urllib.request.urlopen(base + '/truncated')\n        print('opened', len(r.read()))\n"
                "    except Exception:\n        print('failed')\n    return 0\n\nsys.exit(main())\n")
        # Exception is not a name of the typed path: spell the kinds that exist
        prog = prog.replace("except Exception:", "except OSError:")
        src, built = self.program("truncated", prog, irs=("1",))
        got = subprocess.run([str(built["1"])], input=SERVER.base.encode(), capture_output=True, timeout=60, env=program_env())
        self.assertEqual(got.stdout.decode().strip(), "failed", got.stderr.decode())


class RequestTests(Base):
    def test_request_shapes_against_the_echo_server(self):
        for kind in range(22):
            with self.subTest(kind=kind):
                out = self.compare("requests", REQUESTS, lines_of(SERVER.base, str(kind)))
                self.assertIn("method", out)

    def test_wire_bytes_of_the_request_are_cpython_s(self):
        """The head and body each client sends, byte for byte (header names, order, values, Host, Content-Length)."""
        src, built = self.program("rawreq", RAWREQ)
        env = program_env()
        for kind in range(23):
            with self.subTest(kind=kind):
                RAW.take()
                stdin = lines_of(RAW.base, str(kind)).encode()
                want = subprocess.run([sys.executable, str(src)], input=stdin, capture_output=True, timeout=120, env=env)
                self.assertEqual(want.returncode, 0, want.stderr.decode()[-1500:])
                seen_cpython = RAW.take()
                for ir, exe in built.items():
                    got = subprocess.run([str(exe)], input=stdin, capture_output=True, timeout=120, env=env)
                    self.assertEqual(got.returncode, 0, got.stderr.decode()[-1500:])
                    seen_ail = RAW.take()
                    self.assertEqual(len(seen_cpython), 1)
                    self.assertEqual(len(seen_ail), 1, "AIL_IR=%s" % ir)
                    a, b = seen_cpython[0], seen_ail[0]
                    host_a, host_b = hostless(a), hostless(b)
                    a, b = host_a[0], host_b[0]
                    self.assertEqual(host_a[1], host_b[1], "Host line, AIL_IR=%s kind %d" % (ir, kind))
                    if kind == 15:           # 1.5 MB body: compare the head and the body hash
                        self.assertEqual(a.partition(b"\r\n\r\n")[0], b.partition(b"\r\n\r\n")[0], "AIL_IR=%s" % ir)
                        self.assertEqual(a.partition(b"\r\n\r\n")[2], b.partition(b"\r\n\r\n")[2])
                    else:
                        self.assertEqual(a, b, "AIL_IR=%s kind %d\nCPython %r\nAIL     %r" % (ir, kind, a, b))
                    self.assertEqual(got.stdout, want.stdout)
                    self.assertIn(b"User-Agent: Python-urllib/3.12", a) if kind in (0, 1) else None


class RedirectTests(Base):
    def test_redirect_policy(self):
        paths = [
            redir(301, "/echo?a=1"), redir(302, "/echo?b=2"), redir(303, "/echo?c=3"), redir(307, "/echo?d=4"), redir(308, "/echo?e=5"),
            redir(302, SERVER.base + "/echo?abs=1"),
            redir(302, "echo?relative=1"),
            redir(302, "/echo?q=a b"),
            redir(302, "/echo/caf\xe9"),
            redir(302, "/echo/%e3%81%82?x=%7E"),
            redir(302, "?only=query"),
            redir(302, "/echo#frag"),
            redir(302, "/echo?x=1#frag2"),
            redir(302, "file:///etc/passwd"),
            redir(302, "javascript:alert(1)"),
            redir(302, ""),
            redir(302, "//127.0.0.1:%d/echo?netloc=1" % SERVER.port),
            redir(302, "http://127.0.0.1:%d" % SERVER.port),
            redir(302, "/echo?a=1&b=%20"),
            "/status/302", "/status/301?location=%2Fhops%2F2", "/status/303?location=..%2Fecho",
            "/hops/1", "/hops/3?code=301", "/hops/9", "/hops/10", "/hops/11", "/hops/12?code=307", "/hops/4?code=303", "/loop",
        ]
        out = self.compare("fetch", FETCH, lines_of(SERVER.base, *paths))
        self.assertIn("HTTPError 302", out)

    def test_redirects_of_requests_with_data_and_methods(self):
        prog = r'''import sys
import urllib.request
import urllib.error


def go(base: str, code: int, kind: int) -> None:
    to = base + "/echo?after=" + str(code)
    url = base + "/redir?code=" + str(code) + "&to=" + to.replace("/", "%2F").replace("?", "%3F").replace("=", "%3D")
    print("==", code, kind)
    try:
        if kind == 0:
            r = urllib.request.Request(url, data=b"body-data", headers={"X-Keep": "yes", "Content-Type": "text/x-test"})
        elif kind == 1:
            r = urllib.request.Request(url, headers={"X-Keep": "yes"})
        elif kind == 2:
            r = urllib.request.Request(url, method="HEAD", headers={"X-Keep": "yes"})
        elif kind == 3:
            r = urllib.request.Request(url, method="PUT", data=b"put-data")
        elif kind == 4:
            r = urllib.request.Request(url, method="DELETE")
        else:
            r = urllib.request.Request(url, data=b"x", method="GET")
        with urllib.request.urlopen(r, timeout=30) as resp:
            print("status", resp.status, resp.geturl().replace(base, "BASE"))
            print(resp.read().decode())
    except urllib.error.HTTPError as e:
        print("HTTPError", e.code, e.reason, e.url.replace(base, "BASE"))


def main() -> int:
    base = sys.stdin.read().strip()
    for code in (301, 302, 303, 307, 308):
        for kind in range(6):
            go(base, code, kind)
    return 0


sys.exit(main())
'''
        self.compare("redirdata", prog, lines_of(SERVER.base))


class ParseTests(Base):
    def test_quote_unquote_urlencode_urljoin(self):
        rng = random.Random(20261018)
        alphabet = ["a", "Z", "0", " ", "/", "?", "#", "&", "=", "+", "%", "~", "_", "-", ".", ":", "@", "!", "*", "'", "(", ")", ";", ",",
                    "$", "[", "]", "é", "日", "😀", "%41", "%zz", "%e3%81%82", "%ff", "%C3", "%", "%2", "\\", "\"", "<", ">", "{", "}", "|", "^", "`"]
        lines = []
        for _ in range(400):
            s = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 14)))
            lines.append("q " + s)
            lines.append("u " + s)
        lines += ["q ", "u ", "q /a b/c?d=e&f=g#h", "u %E3%81%82%E3%81%84+%2B%20x", "u %", "u %%41", "u +++", "u é%C3%A9%E9", "u %80%81%ff",
                  "u %c3%28", "u %e3%81", "u a%00b"]
        bases = ["http://a/b/c/d;p?q", "http://a/b/c/", "http://a", "http://a/", "https://h:8/x/y", "http://a/b?x#y", "http://a/b/c/d",
                 "/a/b", "a/b", "", "ftp://f/p/q", "http://a/b/../c/./d"]
        rels = ["g", "./g", "g/", "/g", "//g", "?y", "g?y", "#s", "g#s", "g?y#s", ";x", "g;x", "", ".", "./", "..", "../", "../g", "../..",
                "../../g", "../../../g", "../../../../g", "/./g", "/../g", "g.", ".g", "g..", "..g", "./../g", "./g/.", "g/./h", "g/../h",
                "g;x=1/./y", "g;x=1/../y", "http://x/y", "https://x", "http:g", "http:", "g:h", "mailto:x@y", "  ../x", "a b", "%7Ex",
                "http://a/b/c/d;p?q", "../x?y", "//h/p?q#f", "?", "#", "x?", "x#", "../a/b/../c", "/a/b/../c/", "a/./b/../../c"]
        for base in bases:
            for rel in rels:
                lines.append("j %s\t%s" % (base, rel))
        for _ in range(60):
            lines.append("e %s\t%s\t%s\t%s" % tuple("".join(rng.choice(alphabet) for _ in range(rng.randint(1, 6))) for _ in range(4)))
        # the two keys of the e lines must differ (a dict keeps one)
        lines = [l for l in lines if not (l.startswith("e ") and l[2:].split("\t")[0] == l[2:].split("\t")[2])]
        out = self.compare("parse", PARSE, "\n".join(lines) + "\n")
        self.assertIn("q ", out)

    def test_parse_alone_does_not_link_libcurl(self):
        src, built = self.program("parse", PARSE)
        for exe in built.values():
            self.assertNotIn(b"libcurl", Path(exe).read_bytes())
        fetch_src, fetch_built = self.program("fetch", FETCH)
        for exe in fetch_built.values():
            self.assertIn(b"libcurl", Path(exe).read_bytes())


class TimeoutTests(Base):
    def test_timeouts(self):
        out = self.compare("timeout", TIMEOUT, lines_of(SERVER.base))
        self.assertIn("timed out", out)


class ErrorTests(Base):
    def test_error_handlers_and_odd_urls(self):
        dead = "http://127.0.0.1:%d/dead" % free_port()
        out = self.compare("errors", ERRORS, lines_of(SERVER.base, dead, "/status/404", "/status/500", "/echo", "/redir?code=307&to=%2Fecho"))
        self.assertIn("HTTPError 404", out)


class OddUrlTests(Base):
    def test_urls_http_client_rejects_are_value_errors(self):
        """CPython raises http.client.InvalidURL (not a ValueError, not an OSError) for these; here they are ValueErrors."""
        prog = (SIMPLE_MAIN % ("""    for url in sys.stdin.read().split("@@"):
        try:
            urllib.request.urlopen(url)
            print("opened")
        except ValueError:
            print("ValueError")
        except OSError:
            print("OSError")
"""))
        src, built = self.program("oddurls", prog, irs=("1",))
        urls = "@@".join(["http://127.0.0.1:1/a b", "http://user:pw@127.0.0.1:1/x", "http://127.0.0.1:abc/x", "http://[::1/x", "http://127.0.0.1:1/x	y"])
        got = subprocess.run([str(built["1"])], input=urls.encode(), capture_output=True, timeout=60, env=program_env())
        # a host "user:pw@127.0.0.1" and "[:" are looked up and fail to resolve (an OSError in CPython as well)
        self.assertEqual(got.stdout.decode().split(), ["ValueError", "OSError", "ValueError", "OSError", "ValueError"], got.stderr.decode())


SIMPLE_MAIN = """import sys
import urllib.request
import urllib.error


def main() -> int:
%s    return 0


sys.exit(main())
"""


class ExceptionRootTests(Base):
    def test_except_exception_catches_urllib_errors(self):
        """`except Exception` takes URLError and HTTPError, `str(e)` is CPython's text, a user class beside them keeps its own code."""
        prog = r'''import sys
import urllib.request
import urllib.error


class MyError(Exception):
    pass


class OtherError(MyError):
    pass


def attempt(url: str) -> None:
    try:
        urllib.request.urlopen(url, timeout=30)
        print("ok")
    except MyError:
        print("mine")
    except Exception as e:
        print("Exception:", type(e).__name__, "|", e, "|", str(e))


def user() -> None:
    try:
        raise OtherError("boom")
    except OtherError as e:
        print("user", type(e).__name__, e)


def main() -> int:
    lines = sys.stdin.read().split("\n")
    base = lines[0]
    attempt(base + "/status/404")
    attempt(base + "/status/500")
    attempt(lines[1])
    attempt(base + "/echo")
    user()
    return 0


sys.exit(main())
'''
        dead = "http://127.0.0.1:%d/dead" % free_port()
        out = self.compare("excroot", prog, lines_of(SERVER.base, dead))
        self.assertIn("Exception: HTTPError | HTTP Error 404: Not Found", out)
        self.assertIn("Exception: URLError | <urlopen error [Errno 111] Connection refused>", out)


class RefusalTests(Base):
    def prog(self, body, imports="import urllib.request\nimport urllib.error\n"):
        return imports + "\n\ndef main() -> int:\n" + "".join("    %s\n" % line for line in body.split("\n")) + "    return 0\n\n\nimport sys\nsys.exit(main())\n"

    def test_refused_spellings(self):
        cases = [
            ("opener = urllib.request.build_opener()", "build_opener", "write instead:"),
            ("urllib.request.urlretrieve('http://127.0.0.1/', 'x')", "urlretrieve", "write instead:"),
            ("r = urllib.request.urlopen('http://127.0.0.1/')\nprint(r.headers.get('X'))", "headers.get(name) is None", "write instead: headers.get(name, \"\")"),
            ("r = urllib.request.urlopen('http://127.0.0.1/')\nprint(r.info())", "r.info", "write instead:"),
            ("r = urllib.request.urlopen('http://127.0.0.1/')\nprint(r.getheader('X'))", "getheader(name) is None", "write instead:"),
            ("r = urllib.request.urlopen('http://127.0.0.1/')\nfor line in r:\n    print(line)", "iterating over a response", "write instead:"),
            ("r = urllib.request.urlopen('http://127.0.0.1/')\nprint(r.readline())", "r.readline", "write instead:"),
            ("print(urllib.request.urlopen('http://127.0.0.1/', context=None))", "context", "write instead:"),
            ("print(urllib.request.urlopen('ftp://127.0.0.1/x'))", "ftp", "write instead:"),
            ("print(urllib.request.urlopen('file:///etc/hostname'))", "file", "write instead:"),
            ("r = urllib.request.Request('http://127.0.0.1/', origin_req_host='x')", "origin_req_host", ""),
            ("r = urllib.request.Request('http://127.0.0.1/')\nprint(r.headers)", "req.headers", "write instead:"),
            ("r = urllib.request.Request('http://127.0.0.1/')\nr.data = b'x'", "assigning req.data", "write instead:"),
            ("raise urllib.error.HTTPError('u', 404, 'm', None, None)", "HTTPError", "write instead:"),
            ("x = urllib.error.ContentTooShortError", "ContentTooShortError", ""),
            ("print(urllib.parse.urlparse('http://x'))", "urlparse", "write instead:"),
            ("print(urllib.parse.quote('x', encoding='latin-1'))", "encoding", ""),
            ("print(urllib.parse.parse_qs('a=1'))", "parse_qs", "write instead:"),
            ("print(urllib.parse.urlencode({'a': 1}, doseq=True))", "doseq", ""),
            ("try:\n    urllib.request.urlopen('http://127.0.0.1/')\nexcept urllib.error.HTTPError as e:\n    print(e.args)", "e.args", "write instead:"),
            ("try:\n    urllib.request.urlopen('http://127.0.0.1/')\nexcept urllib.error.URLError as e:\n    print(e.code)", "e.code", "write instead:"),
            ("try:\n    urllib.request.urlopen('http://127.0.0.1/')\nexcept urllib.error.HTTPError as e:\n    x = e", "used as a value", "write instead:"),
            ("f = urllib.request.urlopen", "urlopen", "not built"),
        ]
        for body, needle, hint in cases:
            with self.subTest(body=body):
                imports = "import urllib.request\nimport urllib.error\nimport urllib.parse\n"
                stderr = self.refused(self.prog(body, imports), needle)
                if hint:
                    self.assertIn(hint, stderr)

    def test_imports_that_are_not_built(self):
        for imports, needle in (("import urllib.robotparser\n", "urllib.robotparser"), ("import urllib.response\n", "urllib.response"),
                                ("from urllib import robotparser\n", "robotparser"), ("from urllib.request import *\n", "name what you use")):
            with self.subTest(imports=imports):
                self.refused(imports + "\ndef main() -> int:\n    return 0\n\nimport sys\nsys.exit(main())\n", needle)

    def test_general_path_is_refused_by_name(self):
        text = self.prog("print(urllib.request.urlopen('http://127.0.0.1:1/').status)", "import urllib.request\n")
        src = self.dir / "gen.py"
        src.write_text(text, encoding="utf-8")
        env = dict(os.environ, AIL_IR="1")
        env.pop("AIL_NO_GENERAL", None)
        done = subprocess.run([sys.executable, "-B", str(ROOT / "python" / "pkg-v12" / "pyc.py"), str(self.dir / "gen.exe"),
                               "--file", str(src), "--general-only"], capture_output=True, text=True, timeout=600, env=env)
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("urllib is built on the typed path only", done.stderr)
        self.assertIn("write instead:", done.stderr)

    def test_missing_libcurl_says_how_to_install_it(self):
        text = self.prog("print(urllib.request.urlopen('http://127.0.0.1:1/').status)", "import urllib.request\n")
        stderr = self.refused(text, "libcurl", "apt install libcurl4-openssl-dev", extra_env={"AIL_NO_CURL": "1"})
        self.assertIn("brew install curl", stderr)
        # urllib.parse needs no library
        ok = self.dir / "parse_only.py"
        ok.write_text("import urllib.parse\nprint(urllib.parse.quote('a b'))\n", encoding="utf-8")
        done = build(ok, self.dir / "parse_only", "1", extra_env={"AIL_NO_CURL": "1"})
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(subprocess.run([str(self.dir / "parse_only")], capture_output=True, text=True).stdout, "a%20b\n")


class NothingForOtherProgramsTests(Base):
    def test_programs_without_urllib_carry_nothing(self):
        text = "import sys\n\ndef main() -> int:\n    print(len(sys.stdin.read()))\n    return 0\n\nsys.exit(main())\n"
        src = self.dir / "plain.py"
        src.write_text(text, encoding="utf-8")
        debug = self.dir / "plain.d"
        done = build(src, self.dir / "plain", "1", extra=("--debug-dir", str(debug)))
        self.assertEqual(done.returncode, 0, done.stderr)
        c = (debug / "program.c").read_text(encoding="utf-8")
        for token in ("curl", "ailh_", "ailu_", "URLError", "HTTPError"):
            self.assertNotIn(token, c)
        self.assertNotIn(b"libcurl", (self.dir / "plain").read_bytes())

    def test_the_pass_leaves_other_trees_alone(self):
        sys.path.insert(0, PKG)
        try:
            import ast
            import urllower
            tree = ast.parse("import os\nimport json\nx = os.getcwd()\n")
            before = ast.dump(tree)
            self.assertFalse(urllower.rewrite_tree(tree, ValueError))
            self.assertEqual(ast.dump(tree), before)
            self.assertFalse(urllower.ACTIVE)
            unused = ast.parse("import urllib.request\nx = 1\n")
            before = ast.dump(unused)
            self.assertFalse(urllower.rewrite_tree(unused, ValueError))
            self.assertEqual(ast.dump(unused), before)
        finally:
            sys.path.remove(PKG)


# ---------------------------------------------------------------------------------------- HTTPS

HTTPS_PROG = r'''import sys
import urllib.request
import urllib.error


def get(url: str) -> None:
    print("==", url.split("/", 3)[3])
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            print("status", r.status, r.reason, r.headers.get("Content-Type", "-"))
            body = r.read().decode()
            print(len(body), body[:60])
    except urllib.error.HTTPError as e:
        print("HTTPError", e.code, e.reason)
    except urllib.error.URLError as e:
        text = str(e.reason)
        print("URLError", text[:58], "verify" in text)


def main() -> int:
    lines = sys.stdin.read().split("\n")
    for line in lines:
        if line != "":
            get(line)
    return 0


sys.exit(main())
'''


@unittest.skipUnless(OPENSSL, "the openssl command line tool is required to make a test CA and certificates")
class HttpsTests(Base):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        global TLS
        cert = cls.dir / "certs"
        cert.mkdir()

        def run(*args):
            done = subprocess.run([OPENSSL, *args], cwd=cert, capture_output=True, text=True, timeout=120)
            if done.returncode:
                raise unittest.SkipTest("openssl could not make the test certificates: " + done.stderr[-300:])

        run("req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1", "-nodes", "-keyout", "ca.key", "-out", "ca.pem",
            "-days", "2", "-subj", "/CN=ail-test-ca", "-addext", "basicConstraints=critical,CA:TRUE", "-addext", "keyUsage=critical,keyCertSign,cRLSign")
        (cert / "ext.cnf").write_text("subjectAltName=IP:127.0.0.1,DNS:localhost\nbasicConstraints=CA:FALSE\nkeyUsage=critical,digitalSignature\n"
                                      "extendedKeyUsage=serverAuth\n")
        run("req", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1", "-nodes", "-keyout", "srv.key", "-out", "srv.csr", "-subj", "/CN=127.0.0.1")
        run("x509", "-req", "-in", "srv.csr", "-CA", "ca.pem", "-CAkey", "ca.key", "-CAcreateserial", "-out", "srv.pem", "-days", "2", "-extfile", "ext.cnf")
        # a self-signed certificate nobody trusts
        run("req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1", "-nodes", "-keyout", "self.key", "-out", "self.pem",
            "-days", "2", "-subj", "/CN=127.0.0.1", "-addext", "subjectAltName=IP:127.0.0.1")
        # a certificate of the good CA that is valid for another name only
        (cert / "ext2.cnf").write_text("subjectAltName=DNS:other.example\nbasicConstraints=CA:FALSE\nkeyUsage=critical,digitalSignature\nextendedKeyUsage=serverAuth\n")
        run("req", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1", "-nodes", "-keyout", "other.key", "-out", "other.csr", "-subj", "/CN=other.example")
        run("x509", "-req", "-in", "other.csr", "-CA", "ca.pem", "-CAkey", "ca.key", "-CAcreateserial", "-out", "other.pem", "-days", "2", "-extfile", "ext2.cnf")
        cls.certs = cert
        cls.good = Server(str(cert / "srv.pem"), str(cert / "srv.key"))
        cls.selfsigned = Server(str(cert / "self.pem"), str(cert / "self.key"))
        cls.wrongname = Server(str(cert / "other.pem"), str(cert / "other.key"))

    @classmethod
    def tearDownClass(cls):
        for each in (getattr(cls, "good", None), getattr(cls, "selfsigned", None), getattr(cls, "wrongname", None)):
            if each is not None:
                each.close()
        super().tearDownClass()

    def env(self):
        return {"SSL_CERT_FILE": str(self.certs / "ca.pem")}

    def test_https_get_with_a_test_ca(self):
        out = self.compare("https", HTTPS_PROG, lines_of(self.good.base + "/echo", self.good.base + "/status/404", self.good.base + "/utf8",
                                                       self.good.base + "/multi",
                                                       "https://localhost:%d/echo" % self.good.port), env=self.env())
        self.assertIn("status 200 OK", out)
        self.assertIn("HTTPError 404", out)

    def test_untrusted_and_mismatched_certificates_fail_like_cpython(self):
        out = self.compare("https", HTTPS_PROG, lines_of(self.selfsigned.base + "/echo", self.wrongname.base + "/echo",
                                                       "https://localhost:%d/echo" % self.wrongname.port), env=self.env())
        self.assertEqual(out.count("URLError [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed True"), 3, out)

    def test_without_the_ca_the_good_server_is_untrusted(self):
        other = self.certs / "self.pem"
        out = self.compare("https", HTTPS_PROG, lines_of(self.good.base + "/echo"), env={"SSL_CERT_FILE": str(other)})
        self.assertIn("URLError [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed True", out)

    def test_redirect_from_http_to_https(self):
        prog = HTTPS_PROG
        to = self.good.base + "/echo?via=redirect"
        out = self.compare("https", prog, lines_of(SERVER.base + redir(302, to)), env=self.env())
        self.assertIn("status 200 OK", out)


if __name__ == "__main__":
    unittest.main()
