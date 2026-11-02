#!/usr/bin/env python3
"""Build the ail-lang wheel from this checkout in a fresh venv and use it like a user would.

    python3 tools/wheel_check.py            # needs python3 (with venv + pip) and a C compiler; no network
                                            # (pip is told not to look for build dependencies: there are none)

Steps: `pip wheel .` into a temp directory, a fresh venv, `pip install` of that wheel (never of the checkout, so
nothing is imported from the source tree), then with the venv's own `ail`:
  * `ail --version`, `ail doctor --check`,
  * `ail run` of hello world and of a small typed program, compared with CPython,
  * AIL_CURRENT/test_ail_tutorial.py against the installed command (every sample of docs/tutorial.md).
The CI job `wheel` of .github/workflows/tests.yml runs this on Linux; the `wheel` job of
.github/workflows/platforms.yml runs it on Linux, macOS and Windows. A tutorial sample that cannot run on a
platform for a documented reason (no libm on Windows) is skipped there with the reason printed; a sample is
never skipped because AIL prints something different.
"""
import importlib.util
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HELLO = 'print("Hello, AIL!")\n'
TYPED = '''def fib(n: int) -> int:
    a: int = 0
    b: int = 1
    for _ in range(n):
        a, b = b, a + b
    return a


def main() -> None:
    xs: list[int] = [fib(i) for i in range(10)]
    print(xs, sum(xs))
    print(fib(50))


main()
'''

# Platform limitations of a tutorial sample, with the reason, in the same spirit as lab/platforms/config.json.
# Only a platform that cannot run the sample at all is listed, never a difference in what AIL prints.
TUTORIAL_SKIPS = {
    "windows": {
        "ffi": 'the sample calls link("m") and its CPython oracle loads libm with ctypes.util.find_library("m"); '
               'Windows has no libm (the math functions are in the C runtime), so the CPython side cannot run '
               'there (a platform limitation, not a compiler difference)',
    },
}


def platform_name():
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "linux"


def tutorial_sample_tests():
    """[(sample name, unittest method name)] from the tutorial test, using its own parser."""
    path = REPO / "AIL_CURRENT" / "test_ail_tutorial.py"
    spec = importlib.util.spec_from_file_location("_ail_tutorial_for_wheel_check", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return [(sample["name"], "test_sample_" + re.sub(r"\W", "_", sample["name"]))
            for sample in module.tutorial_samples()]


def same_output(got, expected):
    """Compare text after normalizing CRLF: Windows text-mode stdout writes CRLF, as CPython does there."""
    return got.replace("\r\n", "\n") == expected.replace("\r\n", "\n")


def run(cmd, **kwargs):
    print("+", " ".join(str(c) for c in cmd), flush=True)
    done = subprocess.run(cmd, text=True, encoding="utf-8", errors="replace", capture_output=True, **kwargs)
    sys.stdout.write(done.stdout[-3000:])
    sys.stderr.write(done.stderr[-3000:])
    if done.returncode:
        raise SystemExit("failed (exit %d): %s" % (done.returncode, " ".join(str(c) for c in cmd)))
    return done.stdout


def main():
    with tempfile.TemporaryDirectory(prefix="ail-wheel-check-") as tmp:
        tmp = Path(tmp)
        wheels = tmp / "wheels"
        wheels.mkdir()
        venv = tmp / "venv"
        run([sys.executable, "-m", "venv", str(venv)])
        bindir = venv / ("Scripts" if os.name == "nt" else "bin")
        python = bindir / ("python.exe" if os.name == "nt" else "python")
        run([str(python), "-m", "pip", "wheel", "--no-deps", "-w", str(wheels), str(REPO)])
        wheel = sorted(wheels.glob("ail_lang-*.whl"))
        if len(wheel) != 1:
            raise SystemExit("expected one wheel, found %r" % wheel)
        run([str(python), "-m", "pip", "install", str(wheel[0])])
        ail = str(bindir / ("ail.exe" if os.name == "nt" else "ail"))
        work = tmp / "work"
        work.mkdir()
        run([ail, "--version"])
        run([ail, "doctor", "--check"])
        for name, source in (("hello", HELLO), ("typed", TYPED)):
            (work / (name + ".py")).write_text(source, encoding="utf-8")
            expected = run([sys.executable, name + ".py"], cwd=work)
            got = run([ail, "run", "--strict", name + ".py"], cwd=work)
            if not same_output(got, expected):
                raise SystemExit("%s: ail run printed %r, CPython printed %r" % (name, got, expected))
        # PATH and PIPE_CC (the compiler choice of INSTALL.md) reach the venv's ail unchanged.
        env = dict(os.environ, AIL_TUTORIAL_AIL=ail, PYTHONUTF8="1")
        tutorial = str(REPO / "AIL_CURRENT" / "test_ail_tutorial.py")
        skips = TUTORIAL_SKIPS.get(platform_name(), {})
        if skips:
            names = []
            for sample, method in tutorial_sample_tests():
                if sample in skips:
                    print("skip tutorial sample %s on %s: %s" % (sample, platform_name(), skips[sample]), flush=True)
                else:
                    names.append("Tutorial." + method)
            names.append("Structure")
            run([sys.executable, tutorial, *names], env=env, cwd=work)
        else:
            run([sys.executable, tutorial], env=env, cwd=work)
    print("wheel check passed")


if __name__ == "__main__":
    main()
