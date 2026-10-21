"""G7: files and the os module, compared with CPython 3.12.

* `ailfile_core.h` (the C under every open()) is fuzzed against CPython's own `open()`: random mode,
  encoding, errors, newline, buffering and operation scripts over files that cross the 8 KiB chunk
  boundary, executed by a small C driver and by CPython, must print the same result or the same
  exception (class and message) at every step, and leave the same bytes in the file.
* Whole programs - modes r w a x with b and +, encodings, errors=, every newline= setting on read
  and on write (random mixes of CR, LF and CRLF), seek / tell, iteration, `with`, `print(file=)`, the
  OS error classes, os / os.path / os.walk, ntpath and posixpath (against CPython's modules) - are
  built (typed path; AIL_IR=0 and 1) and run, and their stdout must equal CPython's byte for byte.
* A text-file program that only the general path accepts is compared the same way.
* The refusals are checked by name: a mode that is not a literal, an encoding that is not built,
  os names that are not built, a binary file on the general path.
* C18: the whole-file `open(p).read()` reads text with universal newlines.
* Data written to a file that is never closed reaches the disk at exit, also before an uncaught exception.
"""
import os
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")
CORE_DIR = ROOT / "python" / "pkg-v12"


def oracle_env():
    env = dict(os.environ, PYTHONUTF8="1")
    env.pop("PYTHONPATH", None)
    return env


def build(src, exe, ir, typed, extra=(), cwd=None):
    env = dict(os.environ, AIL_IR=ir)
    env.pop("AIL_NO_GENERAL", None)
    env.pop("AIL_TARGET", None)
    if typed:
        env["AIL_NO_GENERAL"] = "1"
    return subprocess.run([sys.executable, "-B", CLI, "compile", str(src), "-o", str(exe), *extra], cwd=cwd,
                          capture_output=True, text=True, timeout=900, env=env)


class ProgramBase(unittest.TestCase):
    def compare(self, name, text, typed=True, irs=("0", "1"), general=False):
        """CPython's stdout for the program equals the compiled program's, for every IR."""
        with tempfile.TemporaryDirectory(prefix="ail-files-") as tmp:
            src = Path(tmp) / (name + ".py")
            src.write_text(text, encoding="utf-8")
            want_dir = Path(tmp) / "oracle"
            want_dir.mkdir()
            want = subprocess.run([sys.executable, str(src), str(want_dir)], cwd=want_dir, capture_output=True,
                                  timeout=300, env=oracle_env())
            self.assertEqual(want.returncode, 0, want.stderr.decode())
            self.assertTrue(want.stdout, "the program prints nothing")
            for ir in irs:
                exe = Path(tmp) / ("exe" + ir)
                built = build(src, exe, ir, typed and not general, cwd=tmp)
                self.assertEqual(built.returncode, 0, "AIL_IR=%s: %s" % (ir, built.stderr[-3000:]))
                if general:
                    self.assertIn("general path", built.stderr)
                run_dir = Path(tmp) / ("run" + ir)
                run_dir.mkdir()
                got = subprocess.run([str(exe), str(run_dir)], cwd=run_dir, capture_output=True, timeout=300)
                self.assertEqual(got.returncode, 0, got.stderr.decode())
                if got.stdout != want.stdout:
                    a = want.stdout.decode("utf-8", "replace").split("\n")
                    b = got.stdout.decode("utf-8", "replace").split("\n")
                    for i in range(max(len(a), len(b))):
                        x = a[i] if i < len(a) else "<none>"
                        y = b[i] if i < len(b) else "<none>"
                        if x != y:
                            self.fail("AIL_IR=%s line %d: CPython %r, AIL %r" % (ir, i + 1, x[:200], y[:200]))
                self.assertEqual(got.stdout, want.stdout)

    def refused(self, text, *needles, general_ok=False):
        with tempfile.TemporaryDirectory(prefix="ail-files-") as tmp:
            src = Path(tmp) / "prog.py"
            src.write_text(text, encoding="utf-8")
            built = build(src, Path(tmp) / "exe", "1", not general_ok, cwd=tmp)
            self.assertNotEqual(built.returncode, 0, built.stdout)
            self.assertFalse((Path(tmp) / "exe").exists())
            self.assertNotIn("Traceback", built.stderr)
            for needle in needles:
                self.assertIn(needle, built.stderr)
            return built.stderr


# ------------------------------------------------------------------------------------ the C core

DRIVER_C = r"""#include "ailfile_core.h"

static int hexv(int c) { return c >= '0' && c <= '9' ? c - '0' : c >= 'a' && c <= 'f' ? c - 'a' + 10 : c - 'A' + 10; }
typedef struct { int none; uint8_t *p; int64_t n; } arg_t;
static arg_t parse_arg(const char *s) {
    arg_t a = {0, NULL, 0};
    if (s[0] == 'N') { a.none = 1; return a; }
    size_t len = strlen(s + 1) / 2;
    a.p = (uint8_t *)malloc(len + 1);
    for (size_t i = 0; i < len; i++) a.p[i] = (uint8_t)(hexv(s[1 + 2 * i]) * 16 + hexv(s[2 + 2 * i]));
    a.p[len] = 0; a.n = (int64_t)len;
    return a;
}
static void hexout(const uint8_t *p, int64_t n) { for (int64_t i = 0; i < n; i++) printf("%02x", p[i]); }
static const char *errname(void) {
    switch (ailf_e.kind) {
    case AILF_E_OS:
        switch (ailf_e.err) {
        case ENOENT: return "FileNotFoundError"; case EACCES: case EPERM: return "PermissionError";
        case EISDIR: return "IsADirectoryError"; case EEXIST: return "FileExistsError"; case ENOTDIR: return "NotADirectoryError";
        default: return "OSError"; }
    case AILF_E_VALUE: return "ValueError"; case AILF_E_UNSUP: return "UnsupportedOperation";
    case AILF_E_UDECODE: return "UnicodeDecodeError"; case AILF_E_UENCODE: return "UnicodeEncodeError";
    default: return "Fatal";
    }
}
static void report_err(void) { printf("err %s %s\n", errname(), ailf_e.msg); }

int main(int argc, char **argv) {
    if (argc < 2) return 2;
    FILE *in = fopen(argv[1], "r");
    if (!in) return 2;
    int64_t h[16]; for (int i = 0; i < 16; i++) h[i] = 0;
    char line[1 << 20];
    while (fgets(line, sizeof line, in)) {
        size_t L = strlen(line); while (L && (line[L - 1] == '\n' || line[L - 1] == '\r')) line[--L] = 0;
        char *f[12]; int nf = 0; char *s = line;
        while (nf < 12) { f[nf++] = s; char *t = strchr(s, '\t'); if (!t) break; *t = 0; s = t + 1; }
        const char *op = f[0];
        int slot = (nf > 1 && strcmp(op, "cat")) ? atoi(f[1]) : 0;
        if (!strcmp(op, "open")) {
            arg_t path = parse_arg(f[2]), mode = parse_arg(f[3]), enc = parse_arg(f[5]), err = parse_arg(f[6]), nl = parse_arg(f[7]);
            int64_t r = ailf_open(path.p, path.n, mode.p, mode.n, atoll(f[4]), enc.p, enc.n, !enc.none, err.p, err.n, !err.none, nl.p, nl.n, !nl.none);
            if (r < 0) report_err(); else { h[slot] = r; printf("ok\n"); }
        } else if (strcmp(op, "cat") && h[slot] == 0) {
            if (!strcmp(op, "close")) puts("ok"); else puts("err ValueError I/O operation on closed file.");
        } else if (!strcmp(op, "cat")) {
            arg_t path = parse_arg(f[1]);
            FILE *c = fopen((char *)path.p, "rb");
            if (!c) { printf("ok -\n"); continue; }
            printf("ok "); int ch; while ((ch = fgetc(c)) != EOF) printf("%02x", ch); printf("\n"); fclose(c);
        } else if (!strcmp(op, "read") || !strcmp(op, "readline") || !strcmp(op, "next")) {
            ailf *fo = ailf_get(h[slot]);
            int istext = fo ? fo->text : 0;
            ailf_buf out = {0}; int rc;
            int64_t n = nf > 2 ? atoll(f[2]) : -1;
            if (!strcmp(op, "read")) rc = istext ? ailf_tread(h[slot], n, &out) : ailf_bread(h[slot], n, &out);
            else if (!strcmp(op, "readline")) rc = istext ? ailf_treadline(h[slot], n, &out) : ailf_breadline(h[slot], n, &out);
            else rc = istext ? ailf_tnext(h[slot], &out) : ailf_bnext(h[slot], &out);
            if (rc) report_err(); else { printf("ok "); hexout(out.p, out.n); printf("\n"); }
            ailf_buf_free(&out);
        } else if (!strcmp(op, "write")) {
            arg_t d = parse_arg(f[2]);
            ailf *fo = ailf_get(h[slot]);
            int64_t r = (fo && fo->text) ? ailf_twrite(h[slot], d.p, d.n) : ailf_bwrite(h[slot], d.p, d.n);
            if (r < 0) report_err(); else printf("ok %lld\n", (long long)r);
        } else if (!strcmp(op, "seek")) {
            ailf *fo = ailf_get(h[slot]);
            int64_t r = (fo && fo->text) ? ailf_tseek(h[slot], atoll(f[2]), atoll(f[3])) : ailf_bseek(h[slot], atoll(f[2]), atoll(f[3]));
            if (r < 0) report_err(); else printf("ok %lld\n", (long long)r);
        } else if (!strcmp(op, "tell")) {
            ailf *fo = ailf_get(h[slot]);
            int64_t r = (fo && fo->text) ? ailf_ttell(h[slot]) : ailf_btell(h[slot]);
            if (r < 0) report_err(); else printf("ok %lld\n", (long long)r);
        } else if (!strcmp(op, "flush")) {
            if (ailf_flush(h[slot])) report_err(); else printf("ok\n");
        } else if (!strcmp(op, "close")) {
            if (ailf_close(h[slot])) report_err(); else printf("ok\n");
        } else if (!strcmp(op, "readable") || !strcmp(op, "writable") || !strcmp(op, "seekable")) {
            int64_t r = !strcmp(op, "readable") ? ailf_readable(h[slot]) : !strcmp(op, "writable") ? ailf_writable(h[slot]) : ailf_seekable(h[slot]);
            if (r < 0) report_err(); else printf("ok %lld\n", (long long)r);
        } else { printf("bad op %s\n", op); return 3; }
    }
    ailf_flush_all();
    return 0;
}
"""


def _hex(b):
    return "S" + b.hex()


def _gen_text(rng, nmax=40):
    toks = ["a", "b", "xyz", "\u00e9", "\u3042", "\U0001F600", "\n", "\r", "\r\n", " ", "\n\n", "\r\r", "\n\r", "\u00fc", "line"]
    return "".join(rng.choice(toks) for _ in range(rng.randint(0, nmax)))


def _gen_content(rng):
    k = rng.random()
    if k < 0.1:
        return b""
    if k < 0.25:                      # crosses the 8192-byte chunk
        parts, size = [], 0
        target = rng.randint(7000, 20000)
        while size < target:
            t = _gen_text(rng, 30).encode("utf-8")
            parts.append(t)
            size += len(t) + 1
            if rng.random() < 0.3:
                parts.append(b"x" * rng.randint(100, 3000))
                size += 100
        return b"".join(parts)
    if k < 0.4:
        return bytes(rng.randrange(256) for _ in range(rng.randint(0, 60)))
    if k < 0.5:
        t = bytearray(_gen_text(rng, 20).encode("utf-8"))
        for _ in range(rng.randint(1, 3)):
            if t:
                t.insert(rng.randrange(len(t) + 1), rng.choice([0xFF, 0x80, 0xC3, 0xE3, 0xE3, 0xF0, 0xED]))
        return bytes(t)
    return _gen_text(rng, 40).encode("utf-8")


# a+ / ab+ files that are read and written alternately differ in when the data reaches the disk
# (documented in DIFFERENCES.md); everything else must agree
MODES = ["r", "w", "a", "x", "r+", "w+", "x+", "rb", "wb", "ab", "xb", "r+b", "rb+", "wb+", "rt", "wt", "at", "r+t"]


def gen_script(rng):
    lines = []
    content = _gen_content(rng)
    mode = rng.choice(MODES)
    enc = rng.choice([None, None, "utf-8", "utf8", "ascii", "latin-1", "Latin1"])
    err = rng.choice([None, None, "strict", "replace", "ignore"])
    nl = rng.choice([None, None, "", "\n", "\r", "\r\n"])
    if "b" in mode and rng.random() < 0.9:
        enc = err = nl = None
    buffering = rng.choice([-1, -1, -1, 1, 0, 4096])
    lines.append("open\t0\t%s\t%s\t%d\t%s\t%s\t%s" % (_hex(b"a.dat"), _hex(mode.encode()), buffering,
                                                     "N" if enc is None else _hex(enc.encode()),
                                                     "N" if err is None else _hex(err.encode()),
                                                     "N" if nl is None else _hex(nl.encode())))
    is_bin = "b" in mode
    for _ in range(rng.randint(1, 14)):
        op = rng.choices(["read", "readline", "next", "write", "seek", "tell", "flush", "readable", "close"],
                         [6, 6, 3, 6, 4, 3, 1, 1, 1])[0]
        if op == "read":
            lines.append("read\t0\t%d" % rng.choice([-1, 0, 1, 2, 3, 5, 100, 10000]))
        elif op == "readline":
            lines.append("readline\t0\t%d" % rng.choice([-1, -1, -1, 0, 1, 2, 5, 100]))
        elif op == "next":
            lines.append("next\t0")
        elif op == "write":
            d = bytes(rng.randrange(256) for _ in range(rng.randint(0, 20))) if is_bin else _gen_text(rng, 12).encode("utf-8")
            lines.append("write\t0\t%s" % _hex(d))
        elif op == "seek":
            lines.append("seek\t0\t%d\t%d" % (rng.choice([0, 0, 0, 1, 2, 5, -1, 3]), rng.choice([0, 0, 1, 2])))
        elif op == "tell":
            lines.append("tell\t0")
        elif op == "flush":
            lines.append("flush\t0")
        elif op == "readable":
            lines.append(rng.choice(["readable", "writable", "seekable"]) + "\t0")
        elif op == "close":
            lines.append("close\t0")
    lines.append("close\t0")
    lines.append("cat\t" + _hex(b"a.dat"))
    return mode, content, lines


def reference(lines, cwd):
    """The script run with CPython's open(): one result line per step."""
    import io
    files, out = {}, []

    def arg(s):
        return None if s == "N" else bytes.fromhex(s[1:])

    cwd_before = os.getcwd()
    os.chdir(cwd)
    try:
        for line in lines:
            f = line.split("\t")
            op = f[0]
            try:
                if op == "open":
                    kw = {}
                    if arg(f[5]) is not None:
                        kw["encoding"] = arg(f[5]).decode()
                    if arg(f[6]) is not None:
                        kw["errors"] = arg(f[6]).decode()
                    if arg(f[7]) is not None:
                        kw["newline"] = arg(f[7]).decode()
                    import warnings
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        files[int(f[1])] = open(arg(f[2]).decode(), arg(f[3]).decode(), int(f[4]), **kw)
                    out.append("ok")
                elif op == "cat":
                    try:
                        with open(arg(f[1]).decode(), "rb") as g:
                            out.append("ok " + g.read().hex())
                    except OSError:
                        out.append("ok -")
                else:
                    fo = files.get(int(f[1]))
                    if fo is None:
                        out.append("ok" if op == "close" else "err ValueError I/O operation on closed file.")
                        continue
                    text = isinstance(fo, io.TextIOBase)
                    if op in ("read", "readline"):
                        n = int(f[2])
                        r = fo.read(n) if op == "read" else fo.readline(n)
                        out.append("ok " + (r.encode("utf-8") if text else r).hex())
                    elif op == "next":
                        try:
                            r = next(fo)
                        except StopIteration:
                            r = "" if text else b""
                        out.append("ok " + (r.encode("utf-8") if text else r).hex())
                    elif op == "write":
                        d = arg(f[2])
                        out.append("ok %d" % fo.write(d.decode("utf-8") if text else d))
                    elif op == "seek":
                        out.append("ok %d" % fo.seek(int(f[2]), int(f[3])))
                    elif op == "tell":
                        out.append("ok %d" % fo.tell())
                    elif op == "flush":
                        fo.flush()
                        out.append("ok")
                    elif op == "close":
                        fo.close()
                        out.append("ok")
                    else:
                        out.append("ok %d" % getattr(fo, op)())
            except BaseException as e:
                out.append("err %s %s" % (type(e).__name__, e))
    finally:
        for fo in files.values():
            try:
                fo.close()
            except Exception:
                pass
        os.chdir(cwd_before)
    return out


class CoreFuzzTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="ail-core-")
        src = Path(cls.tmp.name) / "driver.c"
        src.write_text(DRIVER_C, encoding="utf-8")
        cls.exe = Path(cls.tmp.name) / ("driver.exe" if os.name == "nt" else "driver")
        cc = os.environ.get("PIPE_CC") or shutil.which("gcc") or shutil.which("cc")
        if not cc:
            raise unittest.SkipTest("no C compiler")
        built = subprocess.run([cc, "-O1", "-Wall", "-Wno-unused-function", "-I", str(CORE_DIR), str(src), "-o", str(cls.exe)],
                               capture_output=True, text=True)
        assert built.returncode == 0, built.stderr

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def one(self, seed):
        rng = random.Random(seed)
        mode, content, lines = gen_script(rng)
        results = []
        for who in ("c", "py"):
            with tempfile.TemporaryDirectory(prefix="ail-core-run-") as d:
                if mode[0] != "x":
                    Path(d, "a.dat").write_bytes(content)
                if who == "c":
                    script = Path(d, "script.txt")
                    script.write_text("\n".join(lines) + "\n", encoding="utf-8")
                    p = subprocess.run([str(self.exe), str(script)], cwd=d, capture_output=True, timeout=120)
                    self.assertEqual(p.returncode, 0, p.stderr.decode())
                    results.append(p.stdout.decode("utf-8", "replace").split("\n")[:-1])
                else:
                    results.append(reference(lines, d))
        return mode, lines, results

    def test_core_matches_cpython(self):
        bad = []
        for seed in range(0, 160):
            mode, lines, (got, want) = self.one(seed)
            # CPython packs decoder state into a big tell() cookie when a lone CR is pending
            fixed = []
            for g, w in zip(got, want):
                if w.startswith("ok ") and w[3:].isdigit() and int(w[3:]) >= 2 ** 64 and g.startswith("ok "):
                    g = w
                fixed.append(g)
            fixed += got[len(want):]
            if fixed != want:
                bad.append((seed, mode, lines, fixed, want))
        if bad:
            seed, mode, lines, got, want = bad[0]
            detail = []
            for i, (g, w) in enumerate(zip(got, want)):
                if g != w:
                    detail.append("step %d %r: C %r, CPython %r" % (i, lines[i][:60], g[:80], w[:80]))
                    break
            self.fail("%d of 160 scripts differ; first: seed %d mode %s: %s" % (len(bad), seed, mode, "; ".join(detail)))


# ------------------------------------------------------------------------------------ programs

BASIC = r"""import os
import sys


def write_it(path: str) -> int:
    with open(path, "w", newline="\r\n") as f:
        f.write("one\ntwo\n")
        print("three", 4, 5.5, file=f)
        f.writelines(["a\n", "b\n"])
    with open(path, "rb") as g:
        data = g.read()
    print(len(data))
    return len(data)


def read_it(path: str) -> None:
    f = open(path, newline="")
    first = f.readline()
    print(len(first), first == "one\r\n")
    n = 0
    for line in f:
        n += 1
        print(n, len(line), line.strip())
    f.close()
    print(f.closed)
    with open(path, encoding="utf-8") as g:
        text = g.read()
    print(len(text), text.count("\n"))
    try:
        open(path + ".missing")
    except FileNotFoundError:
        print("no such file")
    try:
        open(path, "x")
    except FileExistsError:
        print("exists")
    try:
        open(os.path.dirname(path))
    except IsADirectoryError:
        print("is a directory")


def main() -> int:
    d = "/tmp/g7p/f1dir"
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "a.txt")
    if os.path.exists(p):
        os.remove(p)
    write_it(p)
    read_it(p)
    print(os.path.getsize(p), os.path.isfile(p), os.path.isdir(d), os.path.basename(p), os.path.splitext(p)[1])
    names = sorted(os.listdir(d))
    print(len(names), names[0])
    os.rename(p, p + ".bak")
    print(os.path.exists(p), os.path.exists(p + ".bak"))
    os.remove(p + ".bak")
    os.rmdir(d)
    print(os.getcwd() == os.path.abspath("."))
    return 0


main()
"""

MODES_PROGRAM = r"""import os
import sys


def show(s: str) -> None:
    for c in s:
        print(ord(c), end=" ")
    print()


def hb(b: bytes) -> None:
    for x in b:
        print(x, end=" ")
    print()


def modes(d: str) -> None:
    p = os.path.join(d, "m.txt")
    with open(p, "w") as f:
        f.write("héllo\nwörld\n")
    with open(p, "a") as f:
        f.write("more\n")
    with open(p, "r") as f:
        print(f.read(3))
        print(f.tell())
        print(f.readline())
        for ln in f.readlines():
            show(ln)
        print(f.read())
    with open(p, "r+") as f:
        f.seek(0)
        f.write("H")
        f.seek(0, 2)
        f.write("end\n")
        f.seek(0)
        print(f.read())
    with open(p, "w+") as f:
        f.write("abc")
        f.seek(1)
        print(f.read())
    with open(p, "a+") as f:
        f.write("def")
        f.seek(0)
        print(f.read())
    try:
        with open(p, "x") as f:
            print("created?")
    except FileExistsError:
        print("exists")
    q = os.path.join(d, "n.txt")
    with open(q, "x") as f:
        f.write("new")
    with open(q, "rb") as f:
        hb(f.read())
        f.seek(1)
        hb(f.read(1))
        print(f.tell())
    with open(q, "wb") as f:
        print(f.write(b"\x00\x01\x02abc"))
    with open(q, "r+b") as f:
        f.seek(3)
        f.write(b"XY")
        f.seek(0)
        hb(f.read())
        f.seek(0)
        hb(f.readline())
    with open(q, "ab") as f:
        f.write(b"\n12\n34")
    with open(q, "rb") as f:
        for line in f:
            hb(line)


def errors(d: str) -> None:
    p = os.path.join(d, "none.txt")
    try:
        open(p)
    except FileNotFoundError:
        print("fnf")
    try:
        open(p, "r")
    except OSError:
        print("oserror")
    try:
        open(d, "w")
    except IsADirectoryError:
        print("isdir")
    try:
        open(os.path.join(d, "no", "such", "x"), "w")
    except FileNotFoundError:
        print("fnf2")
    try:
        open(p, "z")
    except ValueError:
        print("bad mode")
    try:
        open(p, "rw")
    except ValueError:
        print("bad mode 2")
    with open(os.path.join(d, "w.txt"), "w") as f:
        try:
            f.read()
        except OSError:
            print("not readable")
    f = open(os.path.join(d, "w.txt"), "r")
    f.close()
    try:
        f.read()
    except ValueError:
        print("closed")
    try:
        f.write("x")
    except ValueError:
        print("closed w")
    f.close()
    print(f.closed)


def main() -> int:
    d = sys.argv[1]
    modes(d)
    errors(d)
    return 0


main()
"""

OS_PROGRAM = r"""import os
import sys


def touch(p: str, text: str) -> None:
    with open(p, "w") as f:
        f.write(text)


def listing(d: str) -> None:
    names = sorted(os.listdir(d))
    for n in names:
        full = os.path.join(d, n)
        kind = "dir" if os.path.isdir(full) else "file"
        print(n, kind, os.path.isfile(full), os.path.exists(full))


def walk_all(top: str) -> None:
    total = 0
    for root, dirs, files in os.walk(top):
        dirs.sort()
        rel = os.path.relpath(root, top)
        print(rel, len(dirs), len(files))
        for name in sorted(files):
            total += os.path.getsize(os.path.join(root, name))
    print("total", total)


def prune(top: str) -> None:
    for root, dirs, files in os.walk(top):
        dirs.sort()
        keep: list[str] = []
        for d in dirs:
            if d != "skip":
                keep.append(d)
        dirs[:] = keep
        print(os.path.basename(root), len(files))


def main() -> int:
    d = sys.argv[1]
    base = os.path.join(d, "tree")
    os.makedirs(os.path.join(base, "a", "b"))
    os.makedirs(os.path.join(base, "skip", "deep"), exist_ok=True)
    os.makedirs(os.path.join(base, "a", "b"), exist_ok=True)
    touch(os.path.join(base, "f1.txt"), "hello")
    touch(os.path.join(base, "a", "f2.txt"), "world!!")
    touch(os.path.join(base, "a", "b", "f3.txt"), "")
    touch(os.path.join(base, "skip", "deep", "f4.txt"), "xyz")
    listing(base)
    walk_all(base)
    prune(base)
    try:
        os.makedirs(os.path.join(base, "a"))
    except FileExistsError:
        print("exists")
    try:
        os.mkdir(os.path.join(base, "a"))
    except FileExistsError:
        print("exists2")
    try:
        os.listdir(os.path.join(base, "nope"))
    except FileNotFoundError:
        print("no dir")
    try:
        os.listdir(os.path.join(base, "f1.txt"))
    except NotADirectoryError:
        print("not a dir")
    try:
        os.rmdir(os.path.join(base, "a"))
    except OSError:
        print("not empty")
    try:
        os.remove(os.path.join(base, "a"))
    except IsADirectoryError:
        print("is a dir")
    except PermissionError:
        print("perm")
    try:
        os.remove(os.path.join(base, "zzz"))
    except FileNotFoundError:
        print("fnf remove")
    old = os.path.join(base, "f1.txt")
    new = os.path.join(base, "g1.txt")
    os.rename(old, new)
    print(os.path.exists(old), os.path.exists(new))
    os.replace(new, old)
    print(os.path.exists(old), os.path.exists(new))
    os.remove(old)
    print(os.getcwd() == os.path.abspath("."))
    print(os.path.abspath("x/../y") == os.path.join(os.getcwd(), "y"))
    print(os.environ.get("G7_SURELY_UNSET", "dflt"), os.getenv("G7_SURELY_UNSET", "d2"))
    os.environ["G7_TEST_VAR"] = "val"
    print(os.environ["G7_TEST_VAR"], "G7_TEST_VAR" in os.environ, "G7_NOPE" in os.environ)
    del os.environ["G7_TEST_VAR"]
    print("G7_TEST_VAR" in os.environ)
    try:
        v = os.environ["G7_NOPE"]
    except KeyError:
        print("keyerror")
    print(os.sep, os.path.sep, os.linesep == "\n", os.name, os.curdir, os.pardir, os.pathsep)
    print(os.path.join("a", "b", "c"), os.path.join("/a", "b"), os.path.join("a", "/b", "c"))
    head, tail = os.path.split("/x/y/z.tar.gz")
    print(head, tail)
    root, ext = os.path.splitext(tail)
    print(root, ext)
    print(os.path.dirname("/x/y/"), os.path.basename("/x/y/"), os.path.normpath("a/./b/../c//d"), os.path.isabs("/a"), os.path.isabs("a"))
    print(os.path.relpath("/a/b/c", "/a"), os.path.relpath("/a", "/a/b"))
    return 0


main()
"""

MISC_PROGRAM = r"""import os
import sys
from typing import TextIO


def put(out: TextIO, label: str, n: int) -> None:
    print(label, n, file=out)
    out.write(label + "\n")


def count_lines(f: TextIO) -> int:
    n = 0
    for line in f:
        n += 1
    return n


def show(s: str) -> None:
    print(len(s), end=":")
    for c in s:
        print(ord(c), end=" ")
    print()


def encodings(d: str) -> None:
    p = os.path.join(d, "enc.txt")
    with open(p, "w", encoding="latin-1") as f:
        f.write("café ÿ")
    with open(p, "rb") as f:
        raw = f.read()
    print(len(raw), raw[3], raw[5])
    with open(p, encoding="latin-1") as f:
        show(f.read())
    with open(p, "w", encoding="ascii", errors="replace") as f:
        f.write("aébあc")
    with open(p, encoding="ascii") as f:
        show(f.read())
    with open(p, "w", encoding="ascii", errors="ignore") as f:
        f.write("aébあc")
    with open(p, encoding="utf-8") as f:
        show(f.read())
    try:
        with open(p, "w", encoding="ascii") as f:
            f.write("é")
    except ValueError:
        print("encode error")
    with open(p, "wb") as f:
        f.write(b"ok\xffbad\xc3")
    try:
        with open(p) as f:
            f.read()
    except ValueError:
        print("decode error")
    with open(p, errors="replace") as f:
        show(f.read())
    with open(p, errors="ignore") as f:
        show(f.read())
    with open(p, encoding="latin1") as f:
        show(f.read())
    with open(p, encoding="UTF8", errors="strict") as f:
        try:
            f.read()
        except UnicodeDecodeError:
            print("udecode")


def misc(d: str) -> None:
    p = os.path.join(d, "m.txt")
    with open(p, "w") as f:
        put(f, "alpha", 1)
        put(f, "beta", 2)
    with open(p) as f:
        print(count_lines(f))
    with open(p) as f:
        first = next(f)
        show(first)
        rest = list(f)
        print(len(rest))
        for r in rest:
            show(r)
    with open(p) as f:
        for i, line in enumerate(f):
            print(i, len(line))
    with open(p) as f:
        for i, line in enumerate(f, 10):
            print(i, len(line))
    with open(p) as f:
        sizes = [len(line) for line in f]
        print(len(sizes), sizes[0])
    with open(p) as f:
        print("".join(f).count("a"))
    with open(p) as f:
        lst = sorted(f)
        print(len(lst))
    open(p, "w").write("tmp")
    print(open(p).read())
    print(len(open(p, "rb").read()))
    open(p, "a").write("+more")
    print(open(p).read(), len(open(p).readlines()))
    g = open(p)
    print(g.readline())
    g.close()
    print(g.closed, g.name == p, g.mode)
    with open(p, "w") as w:
        w.write("x")
        print(w.closed)
    print(w.closed)
    f2 = open(p, "r")
    with f2:
        print(f2.read())
    print(f2.closed)
    # exit without closing: the data is written at exit
    h = open(os.path.join(d, "unclosed.txt"), "w")
    h.write("unflushed")


def main() -> int:
    d = sys.argv[1]
    encodings(d)
    misc(d)
    return 0


main()
"""

BINARY_PROGRAM = r"""import os
import sys


def hb(b: bytes) -> None:
    print(len(b), end=":")
    for x in b:
        print(x, end=" ")
    print()


def binary(d: str) -> None:
    p = os.path.join(d, "b.bin")
    with open(p, "wb") as f:
        print(f.write(b"line1\nline2\r\nline3"))
        print(f.tell())
        f.seek(0)
        f.write(b"LINE")
        print(f.tell())
        f.seek(2, 1)
        print(f.tell())
        f.seek(-2, 2)
        print(f.tell())
    with open(p, "rb") as f:
        hb(f.read(4))
        print(f.tell())
        hb(f.readline())
        hb(f.readline(3))
        hb(f.readline())
        hb(f.readline())
        hb(f.read())
        f.seek(0)
        for line in f:
            hb(line)
        f.seek(2)
        lines = f.readlines()
        print(len(lines))
        f.seek(0)
        hb(f.read(1000))
        hb(f.read(1))
    with open(p, "r+b") as f:
        f.seek(5)
        f.write(b"__")
        f.seek(0)
        hb(f.read(8))
        f.seek(0, 2)
        print(f.tell())
    with open(p, "ab") as f:
        print(f.tell())
        f.write(b"!!")
        print(f.tell())
    with open(p, "ab+") as f:
        f.seek(0)
        hb(f.read(3))
        f.write(b"?")
    with open(p, "rb") as f:
        hb(f.read())
    with open(p, "wb+") as f:
        f.write(b"abcdef")
        f.seek(2)
        hb(f.read(2))
        f.write(b"XY")
        f.seek(0)
        hb(f.read())
    big = os.path.join(d, "big.bin")
    with open(big, "wb") as f:
        i = 0
        while i < 3000:
            f.write(b"0123456789abcdef")
            i += 1
    with open(big, "rb") as f:
        n = 0
        total = 0
        while True:
            chunk = f.read(5000)
            if len(chunk) == 0:
                break
            n += 1
            total += len(chunk)
        print(n, total)
    with open(big, "rb") as f:
        f.seek(40000)
        hb(f.read(5))
        print(f.tell())
    print(os.path.getsize(big))


def perms(d: str) -> None:
    p = os.path.join(d, "perm.txt")
    with open(p, "w") as f:
        f.write("x")
    os.chmod(p, 0)
    try:
        open(p)
    except PermissionError:
        print("perm read")
    except OSError:
        print("oserror")
    try:
        open(p, "w")
    except PermissionError:
        print("perm write")
    os.chmod(p, 420)


def main() -> int:
    d = sys.argv[1]
    binary(d)
    perms(d)
    return 0


main()
"""

ALIASES_PROGRAM = r"""import io
import os.path as osp
import sys
from os import getcwd, listdir, makedirs, path, remove
from os.path import basename, exists, join, splitext


def main() -> int:
    d = sys.argv[1]
    sub = join(d, "s")
    makedirs(sub)
    p = osp.join(sub, "a.dat")
    with io.open(p, "w") as f, open(join(sub, "b.dat"), "w") as g:
        f.write("one")
        g.write("two")
    print(len(listdir(sub)), basename(p), splitext(p)[1], exists(p), path.exists(p + "x"))
    with open(p) as f, open(join(sub, "b.dat")) as g:
        print(f.read() + g.read())
    remove(p)
    print(exists(p), getcwd() == osp.abspath("."))
    return 0


main()
"""

GENERAL_PROGRAM = r"""import os


class Box:
    def __init__(self, v):
        self.v = v


def show(s):
    print(len(s), [ord(c) for c in s])


mixed = [1, "a", 2.5]
b = Box("x")
b.w = 3

with open("g.txt", "w") as f:
    f.write("héllo\nwörld\r\n")
    print("third", 3, file=f)
    f.writelines(["a\n", "b\n"])

with open("g.txt") as f:
    first = f.readline()
    show(first)
    rest = f.readlines()
    print(len(rest))
    for r in rest:
        show(r)

n = 0
for line in open("g.txt", newline=""):
    n += 1
    show(line)
print(n)

with open("g.txt", "a") as f:
    f.write("tail")
with open("g.txt", "r+") as f:
    f.seek(0, 2)
    print(f.tell())
    f.seek(1)
    print(f.read(3))
try:
    open("missing.txt")
except FileNotFoundError as e:
    print("fnf", e.errno, e.filename)
    print(e)
try:
    open("g.txt", "x")
except FileExistsError as e:
    print("exists", e)
try:
    open(".", "w")
except IsADirectoryError as e:
    print("isdir", e)
except OSError as e:
    print("oserr", e)
try:
    open("g.txt", "q")
except ValueError as e:
    print(e)
f = open("g.txt")
f.close()
print(f.closed)
try:
    f.read()
except ValueError as e:
    print(e)
os.makedirs("sub/dir", exist_ok=True)
with open(os.path.join("sub", "dir", "x.txt"), "w") as f:
    f.write("x")
print(sorted(os.listdir("sub")))
for root, dirs, files in os.walk("sub"):
    print(root, sorted(dirs), sorted(files))
print(os.path.exists("sub/dir/x.txt"), os.path.isdir("sub"), os.path.getsize("sub/dir/x.txt"))
print(os.path.basename("a/b.c"), os.path.dirname("a/b.c"), os.path.splitext("a/b.c"))
print(os.environ.get("NOPE_ZZZ", "dflt"), os.getcwd() == os.path.abspath("."))
os.remove("sub/dir/x.txt")
os.rename("g.txt", "h.txt")
print(os.path.exists("g.txt"), os.path.exists("h.txt"))
"""


def newline_program(seed, count):
    """Every newline= setting, read and write, over random mixes of CR, LF and CRLF."""
    rng = random.Random(seed)
    tokens = ["a", "b", "xy", "\u00e9", "\u3042", "\n", "\r", "\r\n", "\n", "\r", " ", "\u00e9\n", "z\r"]
    cases = ["".join(rng.choice(tokens) for _ in range(rng.randint(0, 25))) for _ in range(count)]
    lines = ["import os\nimport sys\n\n",
             "def show(s: str) -> None:\n    print(len(s), end=\":\")\n    for c in s:\n        print(ord(c), end=\" \")\n    print()\n\n",
             "def hexb(b: bytes) -> None:\n    for x in b:\n        print(x, end=\" \")\n    print()\n\n",
             "def case(i: int) -> bytes:\n"]
    for i, c in enumerate(cases):
        lines.append("    if i == %d:\n        return %r\n" % (i, c.encode("utf-8")))
    lines.append("    return b\"\"\n\n")
    lines.append("def text(i: int) -> str:\n")
    for i, c in enumerate(cases):
        lines.append("    if i == %d:\n        return %r\n" % (i, c))
    lines.append("    return \"\"\n\n")
    lines.append(NEWLINE_BODY % count)
    return "".join(lines)


NEWLINE_BODY = r"""
def read_cases(d: str, i: int) -> None:
    p = os.path.join(d, "n.bin")
    with open(p, "wb") as f:
        f.write(case(i))
    print("case", i)
    with open(p) as f:
        show(f.read())
    with open(p, newline=None) as f:
        n = 0
        for line in f:
            show(line)
            n += 1
        print(n)
    with open(p, newline="") as f:
        show(f.read(3))
        show(f.readline())
        show(f.readline(2))
        show(f.read())
    with open(p, newline="\n") as f:
        show(f.read(2))
        show(f.read())
    with open(p, newline="\r") as f:
        for line in f:
            show(line)
    with open(p, newline="\r\n") as f:
        show(f.readline())
        show(f.read(1))
        show(f.readline())
        show(f.read())
    with open(p, newline="\r\n") as f:
        for line in f:
            show(line)


def write_cases(d: str, i: int) -> None:
    p = os.path.join(d, "w.txt")
    s = text(i)
    with open(p, "w") as f:
        f.write(s)
    with open(p, "rb") as f:
        hexb(f.read())
    with open(p, "w", newline="") as f:
        f.write(s)
    with open(p, "rb") as f:
        hexb(f.read())
    with open(p, "w", newline="\n") as f:
        f.write(s)
    with open(p, "rb") as f:
        hexb(f.read())
    with open(p, "w", newline="\r") as f:
        f.write(s)
        f.write(s)
    with open(p, "rb") as f:
        hexb(f.read())
    with open(p, "w", newline="\r\n") as f:
        f.write(s)
    with open(p, "rb") as f:
        hexb(f.read())
    with open(p, "w", newline="\r\n") as f:
        print(s, end="", file=f)
        print(file=f)
    with open(p, "rb") as f:
        hexb(f.read())


def main() -> int:
    d = sys.argv[1]
    i = 0
    while i < %d:
        read_cases(d, i)
        write_cases(d, i)
        i += 1
    return 0


main()
"""


def path_program(seed, count, flavor):
    """ntpath / posixpath functions on random path strings (the oracle is CPython's own module)."""
    rng = random.Random(seed)
    pieces = ["", "a", "b", "..", ".", "C:", "c:", "C:\\", "C:/", "\\\\host\\share", "\\\\host\\share\\x", "\\\\host", "/", "\\",
              "a/b", "a\\b", "dir\\", "x.txt", ".bashrc", "a.b.c", "\\\\?\\C:\\x", "\\\\.\\dev", "//", "///", "d:", "..\\..",
              "x/./y", "caf\u00e9", "a b", "file.tar.gz", "e.", "...", "/x/", "\\x\\", "//server/share/dir", "\\\\?\\UNC\\h\\s\\d"]
    seps = ["", "/", "\\", "//", "\\\\"]

    def path():
        n = rng.randint(1, 3)
        return "".join(rng.choice(pieces) + (rng.choice(seps) if i < n - 1 else "") for i in range(n))

    m = flavor
    out = ["import %s\nimport sys\n\n" % m,
           "def b(x: str) -> None:\n    print(\"[\" + x + \"]\", end=\" \")\n\n",
           "def one(p: str) -> None:\n    b(%s.basename(p))\n    b(%s.dirname(p))\n    head, tail = %s.split(p)\n    b(head)\n    b(tail)\n" % (m, m, m),
           "    root, ext = %s.splitext(p)\n    b(root)\n    b(ext)\n    b(%s.normpath(p))\n    print(%s.isabs(p))\n\n" % (m, m, m),
           "def two(p: str, q: str, r: str) -> None:\n    b(%s.join(p, q))\n    b(%s.join(p, q, r))\n    b(%s.join(p))\n    print()\n\n" % (m, m, m),
           "def main() -> int:\n"]
    for _ in range(count):
        out.append("    one(%r)\n" % path())
    for _ in range(count // 2):
        out.append("    two(%r, %r, %r)\n" % (path(), path(), path()))
    out.append("    return 0\n\n\nmain()\n")
    return "".join(out)


class FileProgramTests(ProgramBase):
    def test_basic_text_files_and_os(self):
        self.compare("basic", BASIC)

    def test_modes_and_error_classes(self):
        self.compare("modes", MODES_PROGRAM)

    def test_os_and_os_path(self):
        self.compare("os_tree", OS_PROGRAM)

    def test_encodings_iteration_and_temporaries(self):
        self.compare("misc", MISC_PROGRAM)

    def test_binary_files_seek_tell_and_chunks(self):
        self.compare("binary", BINARY_PROGRAM)

    def test_import_spellings(self):
        self.compare("aliases", ALIASES_PROGRAM)

    def test_newline_translation_fuzz(self):
        for seed in (11, 12):
            self.compare("newlines%d" % seed, newline_program(seed, 45))

    def test_posixpath_functions(self):
        self.compare("paths_posix", path_program(5, 220, "posixpath"))

    def test_ntpath_functions(self):
        self.compare("paths_nt1", path_program(6, 220, "ntpath"))
        self.compare("paths_nt2", path_program(7, 220, "ntpath"), irs=("1",))

    def test_general_path_text_files(self):
        self.compare("general", GENERAL_PROGRAM, typed=False, general=True, irs=("1",))


class FileRefusalAndRuntimeTests(ProgramBase):
    def test_refusals_are_named(self):
        self.refused("import sys\n\n\ndef main() -> int:\n    m = sys.argv[1]\n    with open('x', m) as f:\n        f.write('a')\n    print(1)\n    return 0\n\n\nmain()\n",
                     "mode that is not a string literal")
        self.refused("def main() -> int:\n    with open('x', 'w', encoding='cp932') as f:\n        f.write('a')\n    print(1)\n    return 0\n\n\nmain()\n",
                     "only utf-8, ascii and latin-1")
        self.refused("def main() -> int:\n    with open('x', 'w', errors='surrogateescape') as f:\n        f.write('a')\n    print(1)\n    return 0\n\n\nmain()\n",
                     "only 'strict', 'replace' and 'ignore'")
        self.refused("import os\n\n\ndef main() -> int:\n    print(os.popen('ls'))\n    return 0\n\n\nmain()\n", "os.popen is not built")
        self.refused("import os\n\n\ndef main() -> int:\n    x = os.environ.get('HOME')\n    print(1)\n    return 0\n\n\nmain()\n",
                     "without a default")
        self.refused("import os\n\n\ndef main() -> int:\n    for r, d, f in os.walk('.', topdown=False):\n        print(r)\n    return 0\n\n\nmain()\n",
                     "os.walk(top) takes the top directory only")
        self.refused("def main() -> int:\n    with open('x', 'w', closefd=False) as f:\n        f.write('a')\n    print(1)\n    return 0\n\n\nmain()\n",
                     "closefd")

    def test_binary_files_on_the_general_path(self):
        # refused until branch safetynet; the general path has bytes values now (prelude_bytes.py)
        text = ("class Box:\n    def __init__(self, v):\n        self.v = v\n\n\nb = Box(1)\nb.w = 2\nmixed = [1, 'a']\n"
                "with open('x.bin', 'wb') as f:\n    f.write(b'ab\\x00\\xff')\nprint(1)\n"
                "with open('x.bin', 'rb') as f:\n    print(f.read(), f.read())\n"
                "with open('x.bin', 'ab') as f:\n    f.write(bytes([10, 99]))\n"
                "for line in open('x.bin', 'rb'):\n    print(line)\n")
        self.compare("binary_general", text, general=True, irs=("0",))

    def test_whole_file_read_uses_universal_newlines(self):
        """C18: CPython's text mode turns CRLF and a lone CR into LF."""
        text = ('import sys\n\n\ndef main() -> int:\n    p = sys.argv[1] + "/c18.bin"\n'
                '    with open(p, "wb") as f:\n        f.write(b"a\\r\\nb\\rc\\n")\n'
                '    print(len(open(p).read()))\n    print(len(open(p, "rb").read()))\n    return 0\n\n\nmain()\n')
        self.compare("c18", text)

    def run_program(self, text):
        with tempfile.TemporaryDirectory(prefix="ail-files-") as tmp:
            src = Path(tmp) / "prog.py"
            src.write_text(text, encoding="utf-8")
            work = Path(tmp) / "work"
            work.mkdir()
            want = subprocess.run([sys.executable, str(src), str(work)], cwd=work, capture_output=True, env=oracle_env())
            want_files = {p.name: p.read_bytes() for p in work.iterdir()}
            shutil.rmtree(work)
            work.mkdir()
            exe = Path(tmp) / "exe"
            built = build(src, exe, "1", True, cwd=tmp)
            self.assertEqual(built.returncode, 0, built.stderr[-2000:])
            got = subprocess.run([str(exe), str(work)], cwd=work, capture_output=True)
            got_files = {p.name: p.read_bytes() for p in work.iterdir()}
            return want, want_files, got, got_files

    def test_unclosed_files_are_written_at_exit(self):
        text = ('import sys\n\n\ndef main() -> int:\n    f = open(sys.argv[1] + "/u.txt", "w")\n    f.write("not closed")\n'
                '    g = open(sys.argv[1] + "/v.bin", "wb")\n    g.write(b"also not")\n    print("done")\n    return 0\n\n\nmain()\n')
        want, want_files, got, got_files = self.run_program(text)
        self.assertEqual(want.returncode, got.returncode)
        self.assertEqual(want.stdout, got.stdout)
        self.assertEqual(want_files, got_files)
        self.assertEqual(got_files["u.txt"], b"not closed")

    def test_unclosed_file_is_written_before_an_uncaught_exception(self):
        text = ('import sys\n\n\ndef main() -> int:\n    f = open(sys.argv[1] + "/u.txt", "w")\n    f.write("before the error")\n'
                '    n = int("x")\n    print(n)\n    return 0\n\n\nmain()\n')
        want, want_files, got, got_files = self.run_program(text)
        self.assertEqual(want.returncode, 1)
        self.assertEqual(got.returncode, 1)
        self.assertEqual(want_files, got_files)
        self.assertEqual(got_files["u.txt"], b"before the error")

    def test_with_closes_the_file_when_the_body_raises(self):
        text = ('import sys\n\n\ndef main() -> int:\n    p = sys.argv[1] + "/w.txt"\n    try:\n'
                '        with open(p, "w") as f:\n            f.write("kept")\n            n = int("x")\n            f.write("lost")\n'
                '    except ValueError:\n        print("caught")\n    print(open(p).read())\n    return 0\n\n\nmain()\n')
        self.compare("with_raises", text)

    def test_windows_target_builds(self):
        zig = os.environ.get("AIL_ZIG") or shutil.which("zig") or str(Path.home() / "tools" / "zig" / "zig")
        if not Path(zig).exists() and not shutil.which("zig"):
            self.skipTest("no zig for --target windows")
        with tempfile.TemporaryDirectory(prefix="ail-files-") as tmp:
            for name, text, typed in (("typed", BASIC, True), ("general", GENERAL_PROGRAM, False)):
                src = Path(tmp) / (name + ".py")
                src.write_text(text, encoding="utf-8")
                built = build(src, Path(tmp) / (name + ".exe"), "1", typed, extra=("--target", "windows"), cwd=tmp)
                self.assertEqual(built.returncode, 0, built.stderr[-2000:])
                self.assertTrue((Path(tmp) / (name + ".exe")).read_bytes().startswith(b"MZ"))


if __name__ == "__main__":
    unittest.main()
