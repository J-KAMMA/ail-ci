"""Branch covenv2: `os.environ.get(key)` with no default and `Path.home()`.

`os.environ.get(key)` is a str-or-None value.  On the typed path it is a present flag and a
str, and the uses that can be followed are built (`v is None`, `if v:`, `v or default`,
`print(v)`, `str(v)`, an f-string).  A use that cannot be followed keeps the old route: the
general path builds it, and there is no refusal.  `Path.home()` is the text CPython's
`os.path.expanduser('~')` gives (HOME even when empty, else the passwd entry).

Every program is compared with CPython on the typed path (AIL_NO_GENERAL=1), the default
build (typed with general fallback) and the general path (AIL_UNIFIED_FORCE=1).
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")

ENV_CHECKS = r'''import os


def main() -> None:
    v = os.environ.get("COVENV_KEY")
    e = os.environ.get("COVENV_EMPTY")
    m = os.environ.get("COVENV_MISSING")
    print(v is None, e is None, m is None)
    print(v, e, m)
    if v:
        print("v", v)
    else:
        print("no v")
    if e:
        print("e", e)
    else:
        print("no e")
    if m is None:
        print("no m")
    else:
        print("m", m)
    print(v or "fallback")
    print(e or "fallback")
    print(m or "fallback")


main()
'''

ENV_DIRECT = r'''import os


def main() -> None:
    print(os.environ.get("COVENV_KEY"))
    print(os.environ.get("COVENV_MISSING"))
    print(os.environ.get("COVENV_EMPTY"))
    if os.environ.get("COVENV_KEY"):
        print("yes")
    if os.environ.get("COVENV_MISSING") is None:
        print("missing")
    print(os.environ.get("COVENV_KEY") or "fallback")
    print(os.environ.get("COVENV_EMPTY") or "fallback")
    print(str(os.environ.get("COVENV_MISSING")))
    print(f"{os.environ.get('COVENV_MISSING')}")


main()
'''

ENV_LOOP = r'''import os


def main() -> None:
    keys = ["COVENV_KEY", "COVENV_EMPTY", "COVENV_MISSING"]
    for i in range(3):
        v = os.environ.get(keys[i])
        print(i, v is None, v or "none")
    vals = [os.environ.get("COVENV_KEY"), os.environ.get("COVENV_EMPTY"),
            os.environ.get("COVENV_MISSING")]
    print(vals[0] is None, vals[1] is None, vals[2] is None)
    d = {"a": os.environ.get("COVENV_KEY"), "b": os.environ.get("COVENV_MISSING")}
    print(d["a"] is None, d["b"] is None)
    print(d["a"] or "d", d["b"] or "d")
    g = [os.getenv("COVENV_KEY"), os.getenv("COVENV_MISSING")]
    print(g[0] is None, g[1] is None)


main()
'''

ENV_RETURN = r'''import os


def get(k: str) -> str | None:
    return os.environ.get(k)


def show(v: str | None) -> None:
    if v is None:
        print("none")
    else:
        print(v)
    print(v or "fallback")


def main() -> None:
    show(get("COVENV_KEY"))
    show(get("COVENV_MISSING"))


main()
'''

HOME = r'''from pathlib import Path


def main() -> None:
    h = Path.home()
    print(str(h))
    print(str(Path.home()))
    print(str(h / "a"))
    print(str(Path.home() / "a"))
    print(h.name, h.is_absolute())


main()
'''


def build(directory, text, name, mode, extra_env=None):
    source, exe = Path(directory, name + ".py"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    env = dict(os.environ)
    env.pop("AIL_NO_GENERAL", None)
    env.pop("AIL_UNIFIED_FORCE", None)
    if mode == "typed":
        env["AIL_NO_GENERAL"] = "1"
    elif mode == "general":
        env["AIL_UNIFIED_FORCE"] = "1"
    env.update({"AIL_NO_CACHE": "1", "AIL_QUIET_FALLBACK": "1", "AIL_IR": "1"})
    if extra_env:
        env.update(extra_env)
    return subprocess.run([sys.executable, "-B", CLI, "compile", source.name, "--syntax", "python",
                           "-o", exe.name], cwd=directory, capture_output=True, text=True, timeout=900,
                          env=env), exe


class Covenv(unittest.TestCase):
    def check(self, text, name, mode, run_env):
        with tempfile.TemporaryDirectory(prefix="ail-covenv-") as directory:
            oracle = Path(directory, "oracle.py")
            oracle.write_text(text, encoding="utf-8")
            want_env = dict(os.environ, PYTHONUTF8="1")
            want_env.pop("PYTHONPATH", None)
            for key in ("COVENV_KEY", "COVENV_EMPTY", "COVENV_MISSING"):
                want_env.pop(key, None)
            for key, value in run_env.items():
                if value is None:
                    want_env.pop(key, None)
                else:
                    want_env[key] = value
            want = subprocess.run([sys.executable, "-X", "utf8", str(oracle)], capture_output=True,
                                  timeout=300, env=want_env)
            built, exe = build(directory, text, "p_" + name, mode)
            self.assertEqual(built.returncode, 0, "%s/%s: %s%s" % (name, mode, built.stdout[-1000:],
                                                                   built.stderr[-2000:]))
            got_env = dict(os.environ, PYTHONUTF8="1")
            for key in ("COVENV_KEY", "COVENV_EMPTY", "COVENV_MISSING"):
                got_env.pop(key, None)
            for key, value in run_env.items():
                if value is None:
                    got_env.pop(key, None)
                else:
                    got_env[key] = value
            got = subprocess.run([str(exe)], capture_output=True, timeout=300, env=got_env)
            self.assertEqual(got.returncode, want.returncode, "%s/%s: %s" % (name, mode, got.stderr[-500:]))
            self.assertEqual(got.stdout, want.stdout, "%s/%s" % (name, mode))

    def test_environ_get_no_default(self):
        run_env = {"COVENV_KEY": "value", "COVENV_EMPTY": ""}
        for mode in ("typed", "default", "general"):
            with self.subTest(mode=mode):
                self.check(ENV_CHECKS, "checks_" + mode, mode, run_env)

    def test_environ_get_direct_uses(self):
        run_env = {"COVENV_KEY": "value", "COVENV_EMPTY": ""}
        for mode in ("typed", "general"):
            with self.subTest(mode=mode):
                self.check(ENV_DIRECT, "direct_" + mode, mode, run_env)

    def test_environ_get_return(self):
        run_env = {"COVENV_KEY": "value"}
        for mode in ("typed", "general"):
            with self.subTest(mode=mode):
                self.check(ENV_RETURN, "return_" + mode, mode, run_env)

    def test_environ_get_loop_and_containers(self):
        run_env = {"COVENV_KEY": "value", "COVENV_EMPTY": ""}
        for mode in ("default", "general"):
            with self.subTest(mode=mode):
                self.check(ENV_LOOP, "loop_" + mode, mode, run_env)

    def test_path_home(self):
        cases = {}
        cases["unset"] = {"HOME": None}
        cases["empty"] = {"HOME": ""}
        cases["trailing"] = {"HOME": "/tmp/covenv-home/"}
        cases["internal"] = {"HOME": "/tmp//covenv-home///a//"}
        cases["double_root"] = {"HOME": "//covenv-home"}
        cases["triple_root"] = {"HOME": "///covenv-home"}
        cases["relative"] = {"HOME": "covenv-relative-home"}
        cases["root"] = {"HOME": "/"}
        cases["dot"] = {"HOME": "."}
        cases["dotdot"] = {"HOME": ".."}
        cases["spaces"] = {"HOME": "/tmp/covenv home"}
        cases["tilde"] = {"HOME": "~"}
        cases["tilde_sub"] = {"HOME": "~/x"}
        cases["tilde_double"] = {"HOME": "~~"}
        cases["tilde_trailing"] = {"HOME": "~//"}
        cases["not_tilde"] = {"HOME": "/~"}
        for label, run_env in cases.items():
            for mode in ("typed", "general"):
                with self.subTest(home=label, mode=mode):
                    self.check(HOME, "home_%s_%s" % (label, mode), mode, run_env)


if __name__ == "__main__":
    unittest.main()
