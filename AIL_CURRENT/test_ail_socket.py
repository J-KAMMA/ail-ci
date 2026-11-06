"""ffsock1: `import socket` in compiled programs -- blocking TCP on POSIX, against CPython 3.12.

* Every program of `lab/socket/` that matches CPython is built twice (the default build and
  `AIL_UNIFIED_FORCE=1`) and run; stdout and the exit status must equal CPython's.  Every peer in
  those programs is in-process on 127.0.0.1 (or ::1), so nothing outside the loopback is touched.
* `11_int_prefix.py` stops loudly: `int("99999999999999999999")` is beyond int64, so the compiled
  program must exit 1 with the OverflowError message, which the job allows for such a value.
* The refusals are checked by name and carry a `write instead:` line: recv_into, sendfile, a name
  outside the built surface, and `import socket` under a Windows target.
* A program that does not import socket carries none of the socket C.
"""
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")
LAB = ROOT.parent / "lab" / "socket"

MATCHING = [
    "01_echo_client.py",
    "02_echo_server_three.py",
    "03_line_protocol.py",
    "04_big_transfer.py",
    "05_half_close.py",
    "06_timeout.py",
    "07_refused.py",
    "08_reset.py",
    "09_with_closing.py",
    "12_send_partial.py",
]
IPV6 = "10_ipv6.py"
LOUD = "11_int_prefix.py"


def have_compiler():
    return bool(shutil.which("cc") or shutil.which("gcc") or shutil.which("clang"))


def loopback6_works():
    try:
        s = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        s.bind(("::1", 0))
        s.close()
        return True
    except OSError:
        return False


def oracle_env():
    env = dict(os.environ, PYTHONUTF8="1")
    env.pop("PYTHONPATH", None)
    return env


class SocketBase(unittest.TestCase):
    def build(self, src, exe, general=False, extra_env=None):
        env = dict(os.environ, AIL_NO_CACHE="1", AIL_QUIET_FALLBACK="1")
        env.pop("PYTHONPATH", None)
        env.pop("AIL_UNIFIED_FORCE", None)
        env.pop("AIL_TARGET", None)
        if general:
            env["AIL_UNIFIED_FORCE"] = "1"
        if extra_env:
            env.update(extra_env)
        return subprocess.run([sys.executable, "-B", CLI, "compile", str(src), "--syntax", "python",
                               "-o", str(exe)], capture_output=True, text=True, timeout=900, env=env)

    def compile_text(self, tmp, name, text, extra_env=None):
        src = Path(tmp) / name
        src.write_text(text, encoding="utf-8")
        exe = Path(tmp) / (src.stem + ".exe")
        return self.build(src, exe, extra_env=extra_env), src, exe

    def check_program(self, name, general):
        src = LAB / name
        self.assertTrue(src.is_file(), src)
        with tempfile.TemporaryDirectory(prefix="ail-socket-") as tmp:
            want = subprocess.run([sys.executable, str(src)], capture_output=True, timeout=300,
                                  env=oracle_env())
            self.assertEqual(want.returncode, 0, want.stderr.decode("utf-8", "replace"))
            self.assertTrue(want.stdout, "the program prints nothing")
            exe = Path(tmp) / ("exe-g" if general else "exe-d")
            built = self.build(src, exe, general)
            self.assertEqual(built.returncode, 0, "build: %s" % built.stderr[-4000:])
            got = subprocess.run([str(exe)], capture_output=True, timeout=300, env=oracle_env())
            self.assertEqual(got.returncode, want.returncode,
                             "exit: CPython %d, AIL %d\n%s" % (want.returncode, got.returncode,
                                                              got.stderr.decode("utf-8", "replace")))
            a = want.stdout.decode("utf-8", "replace").split("\n")
            b = got.stdout.decode("utf-8", "replace").split("\n")
            for i in range(max(len(a), len(b))):
                x = a[i] if i < len(a) else "<none>"
                y = b[i] if i < len(b) else "<none>"
                if x != y:
                    self.fail("line %d: CPython %r, AIL %r" % (i + 1, x[:300], y[:300]))
            self.assertEqual(got.stdout, want.stdout)


@unittest.skipUnless(have_compiler(), "no C compiler")
class TestPrograms(SocketBase):
    def test_matching_programs(self):
        for name in MATCHING:
            for general in (False, True):
                with self.subTest(program=name, general=general):
                    self.check_program(name, general)

    @unittest.skipUnless(loopback6_works(), "no IPv6 loopback (::1)")
    def test_ipv6(self):
        for general in (False, True):
            with self.subTest(general=general):
                self.check_program(IPV6, general)

    def test_beyond_int64_stops_loudly(self):
        src = LAB / LOUD
        want = subprocess.run([sys.executable, str(src)], capture_output=True, timeout=300,
                              env=oracle_env())
        self.assertEqual(want.returncode, 0)
        self.assertIn(b"99999999999999999999", want.stdout)
        for general in (False, True):
            with tempfile.TemporaryDirectory(prefix="ail-socket-") as tmp:
                exe = Path(tmp) / ("exe-g" if general else "exe-d")
                built = self.build(src, exe, general)
                self.assertEqual(built.returncode, 0, built.stderr[-4000:])
                got = subprocess.run([str(exe)], capture_output=True, timeout=300, env=oracle_env())
                self.assertEqual(got.returncode, 1)
                self.assertIn(b"OverflowError", got.stderr)
                self.assertIn(b"integer overflow in int()", got.stderr)


@unittest.skipUnless(have_compiler(), "no C compiler")
class TestRefusals(SocketBase):
    def refused(self, text, *phrases, extra_env=None):
        with tempfile.TemporaryDirectory(prefix="ail-socket-") as tmp:
            proc, src, exe = self.compile_text(tmp, "refused.py", text, extra_env)
        self.assertNotEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        for phrase in phrases:
            self.assertIn(phrase, proc.stderr)

    def test_recv_into(self):
        self.refused("import socket\ns = socket.socket()\ns.recv_into(bytearray(4), 4)\n",
                     "socket.recv_into() is refused by name", "write instead:")

    def test_sendfile(self):
        self.refused("import socket\ns = socket.socket()\ns.sendfile(None)\n",
                     "socket.sendfile() is refused by name", "write instead:")

    def test_outside_scope(self):
        self.refused("import socket\nsocket.getaddrinfo('localhost', 80)\n",
                     "socket.getaddrinfo is not built", "write instead:")

    def test_module_as_value(self):
        self.refused("import socket\nf = socket\n", "used as a value is not built", "write instead:")

    def test_windows_target(self):
        self.refused("import socket\nprint(socket.AF_INET)\n",
                     "Winsock is a later job", "write instead:", extra_env={"AIL_TARGET": "windows"})

    def test_plain_program_has_no_socket_c(self):
        with tempfile.TemporaryDirectory(prefix="ail-socket-") as tmp:
            src = Path(tmp) / "plain.py"
            src.write_text("xs = [1, 2, 3]\nprint(sum(xs))\n", encoding="utf-8")
            exe = Path(tmp) / "plain.exe"
            dbg = Path(tmp) / "dbg"
            env = dict(os.environ, AIL_NO_CACHE="1")
            env.pop("PYTHONPATH", None)
            proc = subprocess.run([sys.executable, "-B", CLI, "compile", str(src), "--syntax", "python",
                                   "--debug-dir", str(dbg), "-o", str(exe)],
                                  capture_output=True, text=True, timeout=900, env=env)
            self.assertEqual(proc.returncode, 0, proc.stderr[-3000:])
            c_text = (dbg / "program.c").read_text(encoding="utf-8", errors="replace")
            self.assertNotIn("ailsk_", c_text)
            self.assertNotIn("ailt_sp_sock_", c_text)


if __name__ == "__main__":
    unittest.main()
