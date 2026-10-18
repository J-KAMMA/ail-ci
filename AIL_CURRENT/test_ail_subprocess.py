"""G8: subprocess.run and friends, compared with CPython 3.12.

* `ailproc_core.h` (the C under every run()) is checked on its own where it is pure computation:
  `subprocess.list2cmdline` quoting (the Windows command line, bit for bit), the repr of the remaining
  time of a timeout, the repr of bytes.
* Whole programs - exit codes, capture of stdout and stderr as str or bytes, stderr=STDOUT, DEVNULL,
  input= (str and bytes), text/encoding/errors, universal newlines, cwd, env, timeouts, check=True and
  the CalledProcessError / TimeoutExpired attributes and messages, large outputs while the parent
  feeds stdin (pipe deadlock), missing programs - are built (typed path; AIL_IR=0 and 1) and run, and
  their stdout must equal CPython's byte for byte. The child is the Python interpreter itself where the
  program has to run on Windows too; `sh` is used on POSIX only.
* A program that only the general path accepts is compared the same way (messages of the OS errors
  included).
* The refusals are checked by name: shell=True, a str command, Popen, capture_output with stdout=,
  text= that is not a literal, bytes on the general path, ...
* A program that does not use subprocess carries none of the process layer.
"""
import os
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import test_ail_files as base

ROOT = Path(__file__).resolve().parent
CORE_DIR = ROOT / "python" / "pkg-v12"
POSIX = os.name == "posix"


def oracle_env():
    env = dict(os.environ, PYTHONUTF8="1")
    env.pop("PYTHONPATH", None)
    return env


class ProcBase(base.ProgramBase):
    def compare(self, name, text, typed=True, irs=("0", "1"), general=False):
        """CPython's stdout for the program equals the compiled program's, for every IR."""
        text = text.replace("@PY@", repr(sys.executable))
        with tempfile.TemporaryDirectory(prefix="ail-proc-") as tmp:
            src = Path(tmp) / (name + ".py")
            src.write_text(text, encoding="utf-8")
            want_dir = Path(tmp) / "oracle"
            want_dir.mkdir()
            want = subprocess.run([sys.executable, str(src)], cwd=want_dir, capture_output=True, timeout=300, env=oracle_env())
            self.assertEqual(want.returncode, 0, want.stderr.decode())
            self.assertTrue(want.stdout, "the program prints nothing")
            for ir in irs:
                exe = Path(tmp) / ("exe" + ir + (".exe" if os.name == "nt" else ""))
                built = base.build(src, exe, ir, typed and not general, cwd=tmp)
                self.assertEqual(built.returncode, 0, "AIL_IR=%s: %s" % (ir, built.stderr[-3000:]))
                if general:
                    self.assertIn("general path", built.stderr)
                run_dir = Path(tmp) / ("run" + ir)
                run_dir.mkdir()
                got = subprocess.run([str(exe)], cwd=run_dir, capture_output=True, timeout=300, env=oracle_env())
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


# ------------------------------------------------------------------------------------ the C core

DRIVER_C = r"""#include "ailfile_core.h"
#include "ailproc_core.h"

static int hexv(int c) { return c >= '0' && c <= '9' ? c - '0' : c >= 'a' && c <= 'f' ? c - 'a' + 10 : c - 'A' + 10; }
static uint8_t *unhex(const char *s, int64_t *n) {
    size_t len = strlen(s) / 2;
    uint8_t *p = (uint8_t *)malloc(len + 1);
    for (size_t i = 0; i < len; i++) p[i] = (uint8_t)(hexv(s[2 * i]) * 16 + hexv(s[2 * i + 1]));
    p[len] = 0; *n = (int64_t)len;
    return p;
}
int main(int argc, char **argv) {
    char line[1 << 16];
    (void)argc; (void)argv;
    while (fgets(line, sizeof line, stdin)) {
        size_t L = strlen(line); while (L && (line[L - 1] == '\n' || line[L - 1] == '\r')) line[--L] = 0;
        char *op = line, *rest = strchr(line, ' ');
        if (rest) *rest++ = 0; else rest = line + L;
        if (!strcmp(op, "cmdline")) {
            /* arguments as hex, separated by '/', an empty argument is an empty field; "-" is the empty list */
            ailf_buf args = {0}; int64_t n = 0;
            if (strcmp(rest, "-")) {
                char *s = rest;
                for (;;) {
                    char *e = strchr(s, '/');
                    if (e) *e = 0;
                    int64_t k; uint8_t *p = unhex(s, &k);
                    ailf_buf_put(&args, p, k); ailf_buf_putc(&args, 0); n++;
                    free(p);
                    if (!e) break;
                    s = e + 1;
                }
            }
            ailf_buf out; ailp_list2cmdline(args.p ? args.p : (const uint8_t *)"", n, &out);
            for (int64_t i = 0; i < out.n; i++) printf("%02x", out.p[i]);
            printf("\n");
        } else if (!strcmp(op, "float")) {
            char buf[96]; double d; int64_t k; uint8_t *p = unhex(rest, &k);
            uint64_t bits = 0; for (int i = 0; i < 8; i++) bits = (bits << 8) | p[i];
            memcpy(&d, &bits, 8);
            ailp_float_repr(d, buf, sizeof buf);
            printf("%s\n", buf);
        } else if (!strcmp(op, "bytesrepr")) {
            int64_t k; uint8_t *p = unhex(rest, &k); ailf_buf out;
            ailp_repr_bytes(p, k, &out);
            for (int64_t i = 0; i < out.n; i++) printf("%02x", out.p[i]);
            printf("\n");
        }
        fflush(stdout);
    }
    return 0;
}
"""


class CoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="ail-proc-core-")
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

    def ask(self, lines):
        done = subprocess.run([str(self.exe)], input="\n".join(lines) + "\n", capture_output=True, text=True, timeout=120)
        self.assertEqual(done.returncode, 0, done.stderr)
        return done.stdout.split("\n")[:-1]

    def test_list2cmdline_matches_cpython(self):
        rng = random.Random(8)
        pieces = ["", " ", "a", "ab", "\\", "\\\\", "\"", "\\\"", "\t", "x y", "caf\u00e9", "\u65e5\u672c", "'", "=", "&", "C:\\Program Files\\x",
                  "\\\\server\\share", "a\\", "a\\\\", "\"a\"", "\\\"\\", "--opt=\"v w\"", "%PATH%", "^", "|", "<", ">"]
        cases = [[], [""], ["a"], ["a b"], ["a\\"], ["a b\\"], ["a b\\\\"], ["a\"b"], ["a\\\"b"], ["a\\\\\"b"], ["\\"], ["\\\\"], ["\""],
                 ["a", "", "b"], ["", ""], [" "], ["\t"], ["a\tb"], ["\"a b\""], ["x\\ y\\"], ["C:\\Program Files\\App\\", "-x"]]
        for _ in range(400):
            cases.append([rng.choice(pieces) + (rng.choice(pieces) if rng.random() < 0.6 else "") for _ in range(rng.randint(1, 4))])
        lines = ["cmdline " + ("/".join(a.encode("utf-8").hex() for a in case) if case else "-") for case in cases]
        got = self.ask(lines)
        self.assertEqual(len(got), len(cases))
        for case, line in zip(cases, got):
            self.assertEqual(bytes.fromhex(line).decode("utf-8"), subprocess.list2cmdline(case), repr(case))

    def test_float_repr_matches_cpython(self):
        import struct
        rng = random.Random(9)
        values = [0.5, 1.0, 0.1, 0.3, 2.0, 0.49999, 0.4999736799945822, 1e-5, 1e-4, 1.5e-4, 1e16, 1e15, 123456789012345.6, 5e-324, 1.7976931348623157e308,
                  100.0, 0.001, 12345.678, 3.0, 1e22, 1e-7]
        for _ in range(300):
            values.append(rng.uniform(0, 1) * 10 ** rng.randint(-8, 18))
            values.append(rng.randint(1, 10 ** 6) / 1000.0)
        lines = ["float " + struct.pack(">d", v).hex() for v in values]
        for v, got in zip(values, self.ask(lines)):
            self.assertEqual(got, repr(v))

    def test_bytes_repr_matches_cpython(self):
        rng = random.Random(10)
        cases = [b"", b"a", b"it's", b'say "hi"', b"'\"", b"\\", b"\t\n\r", bytes(range(256))]
        for _ in range(200):
            cases.append(bytes(rng.choice([0, 9, 10, 13, 34, 39, 92, 65, 97, 127, 128, 200, 255, 32]) for _ in range(rng.randint(0, 12))))
        got = self.ask(["bytesrepr " + c.hex() for c in cases])
        for c, line in zip(cases, got):
            self.assertEqual(bytes.fromhex(line).decode("latin-1"), repr(c))


# ------------------------------------------------------------------------------------ programs

BASIC = r"""import subprocess
import sys

PY = @PY@

a0 = subprocess.run([PY, "-c", "import sys; sys.stdout.write('héllo\\r\\nworld\\r'); sys.stderr.write('e1\\n')"], capture_output=True)
print(a0.returncode, len(a0.stdout), len(a0.stderr), a0.stdout[0], a0.stdout.decode())
a1 = subprocess.run([PY, "-c", "import sys; sys.stdout.write('héllo\\r\\nworld\\r'); sys.stderr.write('e1\\n')"], capture_output=True, text=True)
print(a1.returncode, len(a1.stdout), len(a1.stderr))
print(a1.stdout, end="")
a2 = subprocess.run([PY, "-c", "import sys; sys.stdout.write('a'); sys.stdout.flush(); sys.stderr.write('b'); sys.stderr.flush(); sys.stdout.write('c')"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
print(a2.stdout)
print(a2)
a3 = subprocess.run([PY, "-c", "print(1)"], stdout=subprocess.DEVNULL)
print(a3.returncode)
print(a3)
a4 = subprocess.run([PY, "-c", "import sys; sys.exit(7)"])
print(a4.returncode, a4)
a5 = subprocess.run([PY, "-c", "import sys; print(sys.stdin.read().upper())"], input=b"abc", capture_output=True)
print(a5.stdout.decode(), end="")
a6 = subprocess.run([PY, "-c", "import sys; print(sys.stdin.read().upper())"], input="abc\n", capture_output=True, text=True)
print(a6.stdout, end="")
a7 = subprocess.run([PY, "-c", "import sys; print(repr(sys.stdin.read()))"], stdin=subprocess.DEVNULL, capture_output=True, text=True)
print(a7.stdout, end="")
a8 = subprocess.run([PY, "-c", "import sys; print(repr(sys.stdin.read()))"], stdin=subprocess.PIPE, capture_output=True, text=True)
print(a8.stdout, end="")
out = subprocess.check_output([PY, "-c", "print('x' * 3)"])
print(out.decode(), end="")
out2 = subprocess.check_output([PY, "-c", "print('x' * 3)"], text=True)
print(out2, end="")
out3 = subprocess.check_output([PY, "-c", "import sys; print(sys.stdin.read())"], input="from input\n", text=True)
print(out3, end="")
a9 = subprocess.run([PY, "-c", "import sys; sys.stderr.write('only err')"], stderr=subprocess.PIPE)
print(a9.stderr.decode())
print(a9)
"""

PORTABLE_ERRORS = r"""import subprocess

PY = @PY@

for code in [0, 1, 2, 42, 255]:
    r = subprocess.run([PY, "-c", "import sys; sys.exit(%d)" % code])
    print(code, r.returncode)
try:
    subprocess.run([PY, "-c", "import sys; sys.exit(3)"], check=True)
except subprocess.CalledProcessError as e:
    print("cpe", e.returncode, len(e.cmd), e.cmd[2])
    print(e)
try:
    subprocess.run([PY, "-c", "import sys; print('o'); print('e', file=sys.stderr); sys.exit(4)"], check=True, capture_output=True, text=True)
except subprocess.CalledProcessError as e:
    print(e.returncode, e.stdout, e.output, e.stderr, end="")
    print(e)
try:
    subprocess.run([PY, "-c", "import sys; sys.stdout.write('raw'); sys.exit(4)"], check=True, stdout=subprocess.PIPE)
except subprocess.CalledProcessError as e:
    print(e.returncode, e.stdout.decode(), e.output.decode())
try:
    subprocess.check_output([PY, "-c", "import sys; print('boom'); sys.exit(5)"], text=True)
except subprocess.CalledProcessError as e:
    print(e.returncode, e.output, end="")
res2 = subprocess.run([PY, "-c", "import sys; sys.exit(9)"], capture_output=True, text=True)
try:
    res2.check_returncode()
except subprocess.CalledProcessError as e:
    print("late", e.returncode, e)
res3 = subprocess.run([PY, "-c", "print('fine')"], capture_output=True, text=True)
res3.check_returncode()
print(res3.stdout, end="")
try:
    subprocess.run(["no_such_program_g8"])
except FileNotFoundError:
    print("fnf")
try:
    subprocess.run([PY, "-c", "pass"], cwd="no_such_dir_g8")
except OSError:
    print("bad cwd")
try:
    subprocess.run([])
except IndexError:
    print("empty")
try:
    subprocess.run([PY, "a\0b"])
except ValueError:
    print("nul")
tt = subprocess.run([PY, "-c", "print('fast')"], capture_output=True, text=True, timeout=60)
print(tt.stdout, end="")
try:
    subprocess.run([PY, "-c", "import sys,time; sys.stdout.write('part'); sys.stdout.flush(); time.sleep(60)"], capture_output=True, timeout=1.0)
except subprocess.TimeoutExpired as e:
    print("timeout", e.timeout, len(e.cmd))
    print(e)
try:
    subprocess.run([PY, "-c", "import time; time.sleep(60)"], timeout=0.5)
except subprocess.TimeoutExpired:
    print("timeout2")
try:
    subprocess.run([PY, "-c", "import time; time.sleep(60)"], timeout=0.5, stdout=subprocess.PIPE, text=True)
except subprocess.SubprocessError:
    print("timeout3")
"""

POSIX_ERRORS = r"""import subprocess
import os

PY = @PY@

try:
    subprocess.run(["sh", "-c", "kill -9 $$"], check=True)
except subprocess.SubprocessError as e:
    print(e)
res = subprocess.run(["sh", "-c", "kill -15 $$"])
print(res.returncode)
res2 = subprocess.run(["sh", "-c", "echo out; echo err >&2; exit 3"], capture_output=True, text=True)
print(res2.returncode, res2.stdout, res2.stderr, end="")
print(res2)
os.mkdir("sub")
c = subprocess.run([PY, "-c", "import os; print(os.path.basename(os.getcwd()))"], cwd="sub", capture_output=True, text=True)
print(c.stdout, end="")
e1 = subprocess.run([PY, "-c", "import os; print(os.environ.get('G8_A'), os.environ.get('G8_B'), os.environ.get('HOME'))"],
                    env={"G8_A": "1", "G8_B": "two words"}, capture_output=True, text=True)
print(e1.stdout, end="")
os.environ["G8_INHERIT"] = "yes"
e2 = subprocess.run([PY, "-c", "import os; print(os.environ.get('G8_INHERIT'))"], capture_output=True, text=True)
print(e2.stdout, end="")
e3 = subprocess.run(["env"], env={"PATH": "/usr/bin:/bin", "G8_ONLY": "x"}, capture_output=True, text=True)
print(e3.stdout, end="")
e4 = subprocess.run(["echo", "found by PATH"], env={"PATH": "/usr/bin:/bin"}, capture_output=True, text=True)
print(e4.stdout, end="")
with open("notexec.sh", "w") as f:
    f.write("#!/bin/sh\necho hi\n")
try:
    subprocess.run(["./notexec.sh"])
except PermissionError:
    print("permission")
try:
    subprocess.run(["notexec.sh/x"])
except NotADirectoryError:
    print("notadir")
except OSError:
    print("oserror")
"""

LARGE = r"""import subprocess

PY = @PY@

# 3 MB on stdout and 2 MB on stderr, written alternately by a child that also reads 4 MB of stdin
child = (
    "import sys\n"
    "data = sys.stdin.buffer.read()\n"
    "sys.stdout.buffer.write(data[:1000000])\n"
    "for i in range(30):\n"
    "    sys.stdout.buffer.write(b'o' * 100000)\n"
    "    sys.stderr.buffer.write(b'e' * 66666)\n"
    "    sys.stdout.flush()\n"
    "    sys.stderr.flush()\n"
    "sys.stdout.buffer.write(data[-5:])\n"
    "sys.exit(len(data) % 251)\n"
)
payload = "0123456789abcdef" * 262144
r = subprocess.run([PY, "-c", child], input=payload, capture_output=True, text=True)
print(r.returncode, len(r.stdout), len(r.stderr))
print(r.stdout[:20], r.stdout[-7:])
print(r.stderr.count("e"))
rb = subprocess.run([PY, "-c", child], input=payload.encode(), capture_output=True)
print(rb.returncode, len(rb.stdout), len(rb.stderr), rb.stdout[-1], rb.stderr[5])
# a child that never reads its stdin while the parent sends a lot: the pipe closes, nothing hangs
rn = subprocess.run([PY, "-c", "print('done')"], input=payload, capture_output=True, text=True)
print(rn.returncode, rn.stdout, end="")
# many small children
total = 0
for i in range(20):
    ri = subprocess.run([PY, "-c", "print(%d * 2)" % i], capture_output=True, text=True)
    total += int(ri.stdout)
print(total)
"""

TEXT = r"""import subprocess

PY = @PY@

w = subprocess.run([PY, "-c", "import sys; sys.stdout.buffer.write(b'caf\\xe9 ok\\r\\nx\\r')"], capture_output=True, encoding="latin-1")
print(len(w.stdout), ord(w.stdout[3]), w.stdout.count("\n"))
w2 = subprocess.run([PY, "-c", "import sys; sys.stdout.buffer.write(b'a\\xffb\\xc3')"], capture_output=True, text=True, errors="replace")
print(len(w2.stdout), ord(w2.stdout[1]), ord(w2.stdout[3]))
w3 = subprocess.run([PY, "-c", "import sys; sys.stdout.buffer.write(b'a\\xffb\\xc3')"], capture_output=True, text=True, errors="ignore")
print(w3.stdout)
try:
    w4 = subprocess.run([PY, "-c", "import sys; sys.stdout.buffer.write(b'a\\xffb')"], capture_output=True, text=True)
    print("no error")
except UnicodeDecodeError:
    print("decode error")
try:
    w5 = subprocess.run([PY, "-c", "import sys; sys.stdout.buffer.write(b'ok\\x80')"], capture_output=True, text=True, encoding="ascii")
    print("no error")
except ValueError:
    print("ascii decode error")
u = subprocess.run([PY, "-c", "import sys; sys.stdout.write(sys.stdin.read()[::-1])"], input="日本語🙂abc", capture_output=True, text=True)
print(u.stdout)
u2 = subprocess.run([PY, "-c", "import sys; sys.stdout.write(sys.argv[1] + '|' + str(len(sys.argv[1])))", "ünï☃"], capture_output=True, text=True)
print(u2.stdout)
u3 = subprocess.run([PY, "-c", "import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())"], input="é", capture_output=True, encoding="latin-1")
print(len(u3.stdout), ord(u3.stdout[0]))
try:
    u4 = subprocess.run([PY, "-c", "pass"], input="é", capture_output=True, encoding="ascii")
    print("no error")
except ValueError:
    print("encode error")
n = subprocess.run([PY, "-c", "import sys; sys.stdout.write('a\\r\\nb\\rc\\nd')"], capture_output=True, text=True)
print(n.stdout.count("\n"), len(n.stdout))
nb = subprocess.run([PY, "-c", "import sys; sys.stdout.write('a\\r\\nb\\rc\\nd')"], capture_output=True)
print(len(nb.stdout))
"""

SPELLINGS = r"""import subprocess as sp
from subprocess import run, PIPE, STDOUT, DEVNULL, CalledProcessError, TimeoutExpired, SubprocessError, check_output

PY = @PY@


def length_of(r: sp.CompletedProcess[str]) -> int:
    return len(r.stdout)


def code_of(r: sp.CompletedProcess) -> int:
    return r.returncode


def child(text: str) -> sp.CompletedProcess[str]:
    return run([PY, "-c", "print('" + text + "')"], stdout=PIPE, text=True)


x = child("hello")
print(length_of(x), code_of(x))
x2 = run([PY, "-c", "print(1)"], stdout=PIPE, text=True)
print(x2)
y = sp.run([PY, "-c", "import sys; print('o'); print('e', file=sys.stderr)"], stdout=PIPE, stderr=STDOUT, text=True)
print(y.stdout, end="")
print(check_output([PY, "-c", "print(5)"], text=True), end="")
try:
    run([PY, "-c", "import sys; sys.exit(2)"], check=True)
except (CalledProcessError, TimeoutExpired) as e:
    print("caught", e)
try:
    run([PY, "-c", "import sys; sys.exit(2)"], check=True, timeout=30)
except SubprocessError as e:
    print("sub", e)
z = run([PY, "-c", "print('z')"], stdout=PIPE, universal_newlines=True)
print(z.stdout, end="")
"""

GENERAL = r"""import subprocess
import os
from subprocess import run, PIPE, CalledProcessError, TimeoutExpired

PY = @PY@


class Force:
    def __repr__(self) -> str:
        return "F"


def show(r):
    print(r.returncode, r.stdout, r.stderr)


r = run([PY, "-c", "import sys; print('out'); print('err', file=sys.stderr); sys.exit(2)"], stdout=PIPE, stderr=PIPE, text=True)
show(r)
print(r)
print(repr(r), str(r))
try:
    run(["no_such_program_g8"])
except FileNotFoundError as e:
    print(e, e.errno, e.filename)
try:
    run([PY, "-c", "pass"], cwd="no_such_dir_g8")
except FileNotFoundError as e:
    print(e, e.filename)
with open("notexec.sh", "w") as f:
    f.write("#!/bin/sh\necho hi\n")
try:
    run(["./notexec.sh"])
except PermissionError as e:
    print(e, e.errno)
try:
    run(["notexec.sh/x"])
except OSError as e:
    print("E", e)
try:
    run([PY, "-c", "import sys; sys.exit(3)"], check=True)
except CalledProcessError as e:
    print(e, e.returncode, e.cmd)
try:
    run([PY, "-c", "import sys; print('ab'); print('cd', file=sys.stderr); sys.exit(3)"], check=True, capture_output=True, text=True)
except CalledProcessError as e:
    print(e, repr(e.output), repr(e.stdout), repr(e.stderr))
try:
    run(["sh", "-c", "kill -SEGV $$"], check=True)
except CalledProcessError as e:
    print(e)
try:
    run(["sh", "-c", "kill -64 $$"], check=True)
except CalledProcessError as e:
    print(e)
try:
    run(["sh", "-c", "echo before; sleep 30"], timeout=0.7, stdout=PIPE, text=True)
except TimeoutExpired as e:
    print(e, e.timeout, e.cmd)
try:
    run(["sh", "-c", "sleep 30"], timeout=1)
except subprocess.TimeoutExpired as e:
    print("E", e.cmd)
try:
    run([PY, "-c", "import sys; sys.exit(1)"], check=True)
except Exception as e:
    print("generic", "E", e)
try:
    run([PY, "-c", "import sys; sys.exit(1)"], check=True)
except subprocess.SubprocessError as e:
    print("sub", e)
try:
    run([PY, "-c", "import sys; sys.exit(1)"], check=True)
except (OSError, CalledProcessError) as e:
    print("tuple", e)
try:
    run([PY, "-c", "pass", "a\0b"])
except ValueError as e:
    print(e)
try:
    run([])
except IndexError as e:
    print(e)
try:
    run([PY, "-c", "pass"], env={"A=B": "x"})
except ValueError as e:
    print(e)
try:
    run([PY, "-c", "import sys; sys.stdout.buffer.write(b'\\xff')"], capture_output=True, text=True)
except ValueError as e:
    print(e)
try:
    run([PY, "-c", "pass"], input="é", capture_output=True, encoding="ascii")
except ValueError as e:
    print(e)
cmd = "echo hi"
if len(cmd) > 100:
    cmd = ["x"]
try:
    run(cmd, capture_output=True, text=True)
except FileNotFoundError as e:
    print(e)
env2 = {"G8_X": "1"}
print(run([PY, "-c", "import os; print(os.environ.get('G8_X'))"], env=env2, capture_output=True, text=True).stdout, end="")
print(subprocess.check_output(["echo", "a  b"], text=True), end="")
"""


ORDER = r"""import subprocess
import sys

PY = @PY@
print("before")
sys.stdout.flush()
r = subprocess.run([PY, "-c", "print('child says hi')"])
print("after", r.returncode)
sys.stdout.flush()
r2 = subprocess.run([PY, "-c", "import sys; sys.stderr.write('to-stderr\\n'); sys.stderr.flush(); print('to-stdout')"], stderr=subprocess.STDOUT)
print("end", r2.returncode)
sys.stdout.flush()
"""


class ProgramTests(ProcBase):
    def test_basic_capture_text_bytes_streams_and_input(self):
        self.compare("basic", BASIC)

    def test_exit_codes_check_and_timeouts(self):
        self.compare("errors", PORTABLE_ERRORS)

    @unittest.skipUnless(POSIX, "uses sh, kill, env and file modes")
    def test_posix_signals_cwd_env_and_os_errors(self):
        self.compare("posix", POSIX_ERRORS)

    def test_large_outputs_with_stdin_do_not_deadlock(self):
        self.compare("large", LARGE)

    def test_text_encodings_errors_and_newlines(self):
        self.compare("text", TEXT)

    def test_output_order_when_the_parent_flushes_first(self):
        self.compare("order", ORDER)
        force = "class Force:\n    def __repr__(self) -> str:\n        return \"F\"\n\n"
        self.compare("order_general", force + ORDER, typed=False, general=True, irs=("1",))

    def test_import_spellings_and_annotations(self):
        self.compare("spellings", SPELLINGS)

    @unittest.skipUnless(POSIX, "uses sh and kill")
    def test_general_path_messages(self):
        self.compare("general", GENERAL, typed=False, general=True, irs=("1",))


# ------------------------------------------------------------------------------------ refusals

class RefusalTests(ProcBase):
    def test_shell_is_refused_by_name(self):
        err = self.refused('import subprocess\nsubprocess.run(["ls"], shell=True)\n', "shell=True", "write instead: a list of args")
        self.assertNotIn("Traceback", err)

    def test_a_command_string_is_refused(self):
        self.refused('import subprocess\nsubprocess.run("ls -l")\n', "command string", "write instead: a list of args")

    def test_other_names_of_the_module_are_refused(self):
        self.refused('import subprocess\np = subprocess.Popen(["ls"])\n', "subprocess.Popen is not built")
        self.refused('import subprocess\nsubprocess.call(["ls"])\n', "subprocess.call is not built")
        self.refused('import subprocess\nx = subprocess.PIPE\n', "subprocess.PIPE is built as the value of")
        self.refused('from subprocess import *\n', "name what you use")
        self.refused('import subprocess\nraise subprocess.CalledProcessError(1, ["x"])\n', "is not built: the program cannot construct one")

    def test_argument_combinations_that_raise_in_cpython_are_refused(self):
        self.refused('import subprocess\nsubprocess.run(["ls"], capture_output=True, stdout=subprocess.PIPE)\n', "capture_output")
        self.refused('import subprocess\nsubprocess.run(["cat"], stdin=subprocess.PIPE, input=b"x")\n', "input arguments may not both be used")
        self.refused('import subprocess\nsubprocess.check_output(["ls"], stdout=subprocess.PIPE)\n', "does not take stdout=")

    def test_text_has_to_be_a_literal(self):
        self.refused('import subprocess\nt = True\nsubprocess.run(["ls"], text=t)\n', "must be True or False written out", "write instead: text=True")

    def test_unknown_and_unbuilt_options_are_named(self):
        self.refused('import subprocess\nsubprocess.run(["ls"], foo=1)\n', "unexpected keyword argument 'foo'")
        self.refused('import subprocess\nsubprocess.run(["ls"], bufsize=0)\n', "bufsize")
        self.refused('import subprocess\nsubprocess.run(["ls"], encoding="cp932", capture_output=True)\n', "only utf-8, ascii and latin-1")
        self.refused('import subprocess\nsubprocess.run(["ls"], timeout=1+2)\n', "bind the timeout to a variable")
        self.refused('import subprocess\nwith open("o.txt", "w") as f:\n    subprocess.run(["ls"], stdout=f)\n', "stdout= is built for subprocess.PIPE")

    def test_exception_attributes_that_would_be_none_are_refused(self):
        self.refused('import subprocess\ntry:\n    subprocess.run(["false"], check=True)\nexcept subprocess.CalledProcessError as e:\n    print(e.stdout)\n',
                     "does not capture this stream", "None")
        self.refused('import subprocess\ntry:\n    subprocess.run(["false"], check=True)\nexcept subprocess.CalledProcessError as e:\n    print(e.args)\n',
                     "e.args is not built")

    def test_bytes_on_the_general_path_are_refused(self):
        text = ('import subprocess\nclass A:\n    def __repr__(self) -> str:\n        return "A"\n'
                'r = subprocess.run(["echo"], capture_output=True)\nprint(r.returncode, A())\n')
        self.refused(text, "the general path has no bytes values", "write instead: text=True", general_ok=True)


class IsolationTests(ProcBase):
    def test_a_program_without_subprocess_carries_none_of_the_process_layer(self):
        text = "def main() -> int:\n    print(len(\"abc\"))\n    return 0\n\n\nmain()\n"
        with tempfile.TemporaryDirectory(prefix="ail-proc-") as tmp:
            src = Path(tmp) / "plain.py"
            src.write_text(text, encoding="utf-8")
            dbg = Path(tmp) / "dbg"
            built = base.build(src, Path(tmp) / "exe", "1", True, extra=("--debug-dir", str(dbg)), cwd=tmp)
            self.assertEqual(built.returncode, 0, built.stderr[-2000:])
            c = (dbg / "program.c").read_text(encoding="utf-8")
            for marker in ("ailp_", "AILPROC_CORE_H", "CalledProcessError", "ailt_sp_"):
                self.assertNotIn(marker, c)

    def test_a_file_program_does_not_carry_the_process_layer(self):
        text = base.BASIC
        with tempfile.TemporaryDirectory(prefix="ail-proc-") as tmp:
            src = Path(tmp) / "files.py"
            src.write_text(text, encoding="utf-8")
            dbg = Path(tmp) / "dbg"
            built = base.build(src, Path(tmp) / "exe", "1", True, extra=("--debug-dir", str(dbg)), cwd=tmp)
            self.assertEqual(built.returncode, 0, built.stderr[-2000:])
            c = (dbg / "program.c").read_text(encoding="utf-8")
            self.assertIn("ailf_open", c)
            for marker in ("ailp_", "AILPROC_CORE_H", "ailt_sp_"):
                self.assertNotIn(marker, c)

    def test_a_subprocess_program_carries_it(self):
        text = "import subprocess\nr = subprocess.run(['true'])\nprint(r.returncode)\n"
        with tempfile.TemporaryDirectory(prefix="ail-proc-") as tmp:
            src = Path(tmp) / "uses.py"
            src.write_text(text, encoding="utf-8")
            dbg = Path(tmp) / "dbg"
            built = base.build(src, Path(tmp) / "exe", "1", True, extra=("--debug-dir", str(dbg)), cwd=tmp)
            self.assertEqual(built.returncode, 0, built.stderr[-2000:])
            c = (dbg / "program.c").read_text(encoding="utf-8")
            self.assertIn("AILPROC_CORE_H", c)

    def test_windows_target_builds(self):
        zig = os.environ.get("AIL_ZIG") or shutil.which("zig") or str(Path.home() / "tools" / "zig" / "zig")
        if not Path(zig).exists() and not shutil.which("zig"):
            self.skipTest("no zig for --target windows")
        text = BASIC.replace("@PY@", repr("python"))
        with tempfile.TemporaryDirectory(prefix="ail-proc-") as tmp:
            src = Path(tmp) / "win.py"
            src.write_text(text, encoding="utf-8")
            built = base.build(src, Path(tmp) / "win.exe", "1", True, extra=("--target", "windows"), cwd=tmp)
            self.assertEqual(built.returncode, 0, built.stderr[-2000:])
            self.assertTrue((Path(tmp) / "win.exe").read_bytes().startswith(b"MZ"))


if __name__ == "__main__":
    unittest.main()
