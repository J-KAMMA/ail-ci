#!/usr/bin/env python3
"""Install the wheel built from this checkout on clean Linux containers and run the smoke checks.

    python3 tools/install_smoke.py                    # the 8 pinned images plus the no-compiler case
    python3 tools/install_smoke.py --images python:3.12-slim-bookworm
    python3 tools/install_smoke.py --engine podman --keep

The wheel is built once on the host with `pip wheel . --no-deps --no-build-isolation`. Each image gets a
`docker run --rm --memory=1500m` (or podman) with the wheel and the check programs mounted read-only, a fresh
venv in /tmp, and `pip install --no-index /w/*.whl`; then the checks print one `CHECK name PASS|FAIL first-error-line`
line. This script parses those lines and prints the table. Exit status is 0 only when every check passes.

The checks are `ail --version`, `ail doctor --check`, `ail run` of hello world, a typed fib plus the int64 edge,
and `AIL_CURRENT/test_ail_tutorial.py` against the installed command (the tutorial from /src/docs/tutorial.md).
The `nocc` case uses python:3.12-slim-bookworm with nothing installed: `ail doctor --check` must fail and name the
missing C compiler, and `ail run` must fail with a message rather than a traceback.
"""
import argparse
import os
import shlex
import subprocess
import sys
import tempfile
import time
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
    print(2**62 + 2**62 - 1)


main()
'''

CHECK_NAMES = ("version", "doctor", "hello", "typed", "tutorial")

IMAGES = [
    ("python:3.10-slim-bookworm",
     "apt-get update -qq && apt-get install -y -qq --no-install-recommends gcc libc6-dev"),
    ("python:3.11-slim-bookworm",
     "apt-get update -qq && apt-get install -y -qq --no-install-recommends gcc libc6-dev"),
    ("python:3.12-slim-bookworm",
     "apt-get update -qq && apt-get install -y -qq --no-install-recommends gcc libc6-dev"),
    ("python:3.13-slim-bookworm",
     "apt-get update -qq && apt-get install -y -qq --no-install-recommends gcc libc6-dev"),
    ("debian:12",
     "apt-get update -qq && apt-get install -y -qq --no-install-recommends python3 python3-venv gcc libc6-dev"),
    ("ubuntu:24.04",
     "apt-get update -qq && apt-get install -y -qq --no-install-recommends python3 python3-venv gcc libc6-dev"),
    ("fedora:41", "dnf install -y python3 gcc"),
    ("alpine:3.20", "apk add --no-cache python3 py3-pip gcc musl-dev"),
]

NOCC = "nocc"
NOCC_IMAGE = "python:3.12-slim-bookworm"

SETUP = r'''
setup() {
    python3 -m venv /tmp/v >/tmp/venv.log 2>&1 || { SETUP_FAIL="venv: $(firstline /tmp/venv.log)"; return 1; }
    /tmp/v/bin/pip install --no-index /w/*.whl >/tmp/pip.log 2>&1 || { SETUP_FAIL="pip install: $(firstline /tmp/pip.log)"; return 1; }
    return 0
}
'''

COMMON = r'''
set -u
export DEBIAN_FRONTEND=noninteractive
export AIL_CACHE=/tmp/ail-cache
cd /tmp

emit() { printf 'CHECK %s %s\n' "$1" "$2"; }
firstline() {
    for f in "$@"; do
        if [ -s "$f" ]; then
            while IFS= read -r line || [ -n "$line" ]; do
                case "$line" in
                    *[![:space:]]*) printf '%s\n' "$line"; return 0 ;;
                esac
            done < "$f"
        fi
    done
    printf '(no output)\n'
}
setup_fail() {
    for name in version doctor hello typed tutorial; do emit "$name" "FAIL $1"; done
}
same() {
    python3 -c 'import sys
a = open(sys.argv[1], "rb").read()
b = open(sys.argv[2], "rb").read()
raise SystemExit(0 if a == b else 1)' "$1" "$2"
}
meta() {
    py=$(python3 -c 'import platform; print(platform.python_version())' 2>/dev/null || printf '?')
    libc=$(ldd --version 2>&1 | { IFS= read -r line || [ -n "$line" ]; printf '%s\n' "$line"; } || printf '?')
    printf 'META python %s\n' "$py"
    printf 'META libc %s\n' "$libc"
}
'''

NORMAL_CHECKS = r'''
version() {
    if /tmp/v/bin/ail --version >/tmp/out 2>/tmp/err; then emit version PASS
    else emit version "FAIL $(firstline /tmp/err /tmp/out)"; fi
}
doctor() {
    /tmp/v/bin/ail doctor --check >/tmp/out 2>/tmp/err; rc=$?
    if [ "$rc" -eq 0 ]; then emit doctor PASS
    else emit doctor "FAIL $(firstline /tmp/err /tmp/out)"; fi
}
hello() {
    python3 /c/hello.py >/tmp/exp 2>/tmp/experr; exprc=$?
    /tmp/v/bin/ail run --strict /c/hello.py >/tmp/got 2>/tmp/err; rc=$?
    if [ "$rc" -eq 0 ] && [ "$exprc" -eq 0 ] && same /tmp/got /tmp/exp; then emit hello PASS
    elif [ -s /tmp/err ]; then emit hello "FAIL $(firstline /tmp/err)"
    else emit hello "FAIL stdout differs from CPython"; fi
}
typed() {
    python3 /c/typed.py >/tmp/exp 2>/tmp/experr; exprc=$?
    /tmp/v/bin/ail run --strict /c/typed.py >/tmp/got 2>/tmp/err; rc=$?
    if [ "$rc" -eq 0 ] && [ "$exprc" -eq 0 ] && same /tmp/got /tmp/exp; then emit typed PASS
    elif [ -s /tmp/err ]; then emit typed "FAIL $(firstline /tmp/err)"
    else emit typed "FAIL stdout differs from CPython"; fi
}
tutorial() {
    AIL_TUTORIAL_AIL=/tmp/v/bin/ail PYTHONUTF8=1 \
        /tmp/v/bin/python /src/AIL_CURRENT/test_ail_tutorial.py >/tmp/out 2>/tmp/err; rc=$?
    if [ "$rc" -eq 0 ]; then emit tutorial PASS
    else emit tutorial "FAIL $(firstline /tmp/err /tmp/out)"; fi
}
'''

NOCC_CHECKS = r'''
version() {
    if /tmp/v/bin/ail --version >/tmp/out 2>/tmp/err; then emit version PASS
    else emit version "FAIL $(firstline /tmp/err /tmp/out)"; fi
}
doctor() {
    /tmp/v/bin/ail doctor --check >/tmp/out 2>/tmp/err; rc=$?
    cat /tmp/out /tmp/err >/tmp/all
    if [ "$rc" -ne 0 ] && grep -qi 'C compiler is unavailable' /tmp/all; then emit doctor PASS
    else emit doctor "FAIL $(firstline /tmp/err /tmp/out)"; fi
}
hello() {
    /tmp/v/bin/ail run /c/hello.py >/tmp/out 2>/tmp/err; rc=$?
    cat /tmp/out /tmp/err >/tmp/all
    if [ "$rc" -ne 0 ] && grep -qi 'no C compiler found' /tmp/all && ! grep -qi 'traceback' /tmp/all; then
        emit hello PASS
    else emit hello "FAIL $(firstline /tmp/err /tmp/out)"; fi
}
typed() { emit typed SKIP; }
tutorial() { emit tutorial SKIP; }
'''


def shell_script(install, checks):
    return "\n".join([
        COMMON,
        SETUP,
        "META_PENDING=1",
        'if ! (%s) >/tmp/install.log 2>&1; then' % install,
        '    printf "CHECK version FAIL install: %s\\n" "$(firstline /tmp/install.log)"',
        '    for name in doctor hello typed tutorial; do printf "CHECK %s FAIL install: %s\\n" "$name" "$(firstline /tmp/install.log)"; done',
        '    exit 0',
        'fi',
        "meta",
        'if ! setup; then setup_fail "$SETUP_FAIL"; exit 0; fi',
        checks,
        "version",
        "doctor",
        "hello",
        "typed",
        "tutorial",
    ])


def image_config(name):
    if name == NOCC:
        return NOCC_IMAGE, None, NOCC_CHECKS
    for image, install in IMAGES:
        if name == image:
            return image, install, NORMAL_CHECKS
    raise SystemExit("unknown image: %s (choose from %s, %s)"
                     % (name, ", ".join(i for i, _ in IMAGES), NOCC))


def build_wheel(directory):
    wheels = directory / "wheels"
    wheels.mkdir()
    cmd = [sys.executable, "-m", "pip", "wheel", ".", "--no-deps", "--no-build-isolation",
           "-w", str(wheels)]
    print("+ " + " ".join(shlex.quote(c) for c in cmd), flush=True)
    done = subprocess.run(cmd, cwd=str(REPO), text=True, capture_output=True)
    sys.stdout.write(done.stdout[-3000:])
    sys.stderr.write(done.stderr[-3000:])
    if done.returncode:
        raise SystemExit("wheel build failed (exit %d)" % done.returncode)
    found = sorted(wheels.glob("ailc-*.whl"))
    if len(found) != 1:
        raise SystemExit("expected one wheel, found %r" % found)
    return found[0]


def parse(output):
    meta = {}
    checks = {}
    for line in output.splitlines():
        if line.startswith("META "):
            parts = line.split(" ", 2)
            if len(parts) == 3:
                meta[parts[1]] = parts[2]
        elif line.startswith("CHECK "):
            parts = line.split(" ", 3)
            if len(parts) >= 3:
                status = parts[2]
                detail = parts[3] if len(parts) > 3 else ""
                checks[parts[1]] = (status, detail)
    return meta, checks


def run_image(engine, name, wheel_dir, checks_dir, keep):
    image, install, checks = image_config(name)
    if install is None:
        install = "true"
    script = shell_script(install, checks)
    container = "ail-smoke-" + name.replace(":", "-").replace("/", "-")
    cmd = [engine, "run", "--rm", "--name", container, "--memory=1500m",
           "-v", "%s:/w:ro" % wheel_dir,
           "-v", "%s:/c:ro" % checks_dir,
           "-v", "%s:/src:ro" % REPO,
           image, "sh", "-c", script]
    started = time.time()
    print("\n+ %s" % " ".join(shlex.quote(c) for c in cmd[:9]), flush=True)
    try:
        done = subprocess.run(cmd, text=True, encoding="utf-8", errors="replace",
                              capture_output=True, timeout=600)
        output = done.stdout + done.stderr
    except subprocess.TimeoutExpired as error:
        output = ((error.stdout or "") if isinstance(error.stdout, str) else "") + \
                 ((error.stderr or "") if isinstance(error.stderr, str) else "")
        output += "\nCHECK version FAIL timeout after 600s\n"
        subprocess.run([engine, "rm", "-f", container], capture_output=True)
    elapsed = time.time() - started
    meta, found = parse(output)
    results = {}
    for check in CHECK_NAMES:
        results[check] = found.get(check, ("FAIL", "check did not run"))
    return meta, results, elapsed, output


def cell(results, check):
    status, detail = results[check]
    return status


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--images", help="comma-separated image tags (or nocc); default: all 8 plus nocc")
    parser.add_argument("--engine", choices=("docker", "podman"), default="docker")
    parser.add_argument("--keep", action="store_true", help="keep the temporary wheel/check directory")
    args = parser.parse_args()

    if args.images:
        names = [name.strip() for name in args.images.split(",") if name.strip()]
    else:
        names = [image for image, _ in IMAGES] + [NOCC]
    for name in names:
        image_config(name)

    temp = Path(tempfile.mkdtemp(prefix="ail-install-smoke-"))
    try:
        wheel = build_wheel(temp)
        checks = temp / "checks"
        checks.mkdir()
        (checks / "hello.py").write_text(HELLO, encoding="utf-8")
        (checks / "typed.py").write_text(TYPED, encoding="utf-8")
        print("wheel: %s" % wheel, flush=True)

        rows = []
        for name in names:
            meta, results, elapsed, output = run_image(
                args.engine, name, temp / "wheels", checks, args.keep)
            rows.append((name, meta, results, elapsed))
            if os.environ.get("AIL_SMOKE_VERBOSE"):
                print(output)

        print("\n%-30s %-8s %-22s %-8s %-8s %-8s %-8s %-8s %6s"
              % ("image", "python", "libc", "version", "doctor", "hello", "typed", "tutorial", "secs"))
        for name, meta, results, elapsed in rows:
            print("%-30s %-8s %-22s %-8s %-8s %-8s %-8s %-8s %6.1f"
                  % (name, meta.get("python", "?"), meta.get("libc", "?")[:22],
                     cell(results, "version"), cell(results, "doctor"), cell(results, "hello"),
                     cell(results, "typed"), cell(results, "tutorial"), elapsed))

        failures = []
        for name, meta, results, elapsed in rows:
            for check in CHECK_NAMES:
                status, detail = results[check]
                if status != "PASS" and status != "SKIP":
                    failures.append("%s %s: %s %s" % (name, check, status, detail))

        print("\nnocc expected: `ail doctor --check` fails and names the C compiler; `ail run` fails without a traceback.")
        if failures:
            print("\nfailures:")
            for line in failures:
                print("  " + line)
            return 1
        print("\nall checks passed")
        return 0
    finally:
        if args.keep:
            print("kept: %s" % temp)
        else:
            import shutil
            shutil.rmtree(temp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
