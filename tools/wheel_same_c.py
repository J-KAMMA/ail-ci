#!/usr/bin/env python3
"""Build the same programs with the checkout compiler and the installed wheel compiler.

    python3 tools/wheel_same_c.py

For every lab/compare/src/*/main.py and the first program (sorted by name) of every lab/stdlib/<module>/
directory, build twice with `--syntax python --debug-dir`: once with AIL_CURRENT/ail_chatgpt.py from this
checkout, once with <venv>/lib/python3.*/site-packages/ail_lang/sdk/ail_chatgpt.py from a freshly built and
installed wheel. Each build runs in its own temporary copy of the source with AIL_NO_CACHE=1 and a 1.5 GB
address-space limit, at most two at a time.

A program matches when the two builds have the same exit code, the two program.c files are byte-identical and
the built programs print the same stdout and exit with the same status. A difference names the program and
the first differing line of program.c.
"""
import concurrent.futures
import difflib
import os
import resource
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
COMPILER = REPO / "AIL_CURRENT" / "ail_chatgpt.py"
LIMIT = 1500000 * 1024


def limit_memory():
    resource.setrlimit(resource.RLIMIT_AS, (LIMIT, LIMIT))


def programs():
    items = []
    for path in sorted((REPO / "lab" / "compare" / "src").glob("*/main.py")):
        items.append(("compare/" + path.parent.name, path))
    for directory in sorted((REPO / "lab" / "stdlib").iterdir()):
        if not directory.is_dir():
            continue
        found = sorted(directory.glob("*.py"))
        if found:
            items.append(("stdlib/" + directory.name, found[0]))
    return items


def make_wheel_venv(root):
    wheels = root / "wheels"
    wheels.mkdir()
    venv = root / "venv"
    subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True, capture_output=True, text=True)
    bindir = venv / ("Scripts" if os.name == "nt" else "bin")
    python = bindir / ("python.exe" if os.name == "nt" else "python")
    done = subprocess.run([str(python), "-m", "pip", "wheel", "--no-deps", "--no-build-isolation",
                           "-w", str(wheels), str(REPO)], capture_output=True, text=True)
    if done.returncode:
        raise SystemExit("pip wheel failed:\n" + done.stderr[-2000:])
    wheel = next(iter(sorted(wheels.glob("ailc-*.whl"))))
    done = subprocess.run([str(python), "-m", "pip", "install", "--no-deps", "--no-index", str(wheel)],
                          capture_output=True, text=True)
    if done.returncode:
        raise SystemExit("pip install failed:\n" + done.stderr[-2000:])
    sdk = subprocess.run([str(python), "-c",
                          "import ail_lang, pathlib; print(pathlib.Path(ail_lang.__file__).parent / 'sdk')"],
                         check=True, capture_output=True, text=True).stdout.strip()
    return python, Path(sdk), wheel


def build(python, compiler, source, work):
    source = Path(source)
    work.mkdir(parents=True, exist_ok=True)
    src = work / source.name
    shutil.copyfile(source, src)
    out = work / "prog"
    debug = work / "debug"
    debug.mkdir()
    env = {k: v for k, v in os.environ.items()
           if k not in ("AIL_CACHE", "AIL_NO_CACHE", "PYTHONPATH", "PYTHONDONTWRITEBYTECODE")}
    env.update(AIL_NO_CACHE="1", PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
    cmd = [str(python), "-B", str(compiler), "compile", str(src), "-o", str(out),
           "--syntax", "python", "--debug-dir", str(debug)]
    done = subprocess.run(cmd, cwd=work, env=env, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=900, preexec_fn=limit_memory)
    program_c = debug / "program.c"
    return {
        "returncode": done.returncode,
        "stderr": done.stderr,
        "program_c": program_c.read_bytes() if program_c.is_file() else None,
        "binary": out if out.is_file() else None,
        "work": work,
    }


def run_binary(result):
    binary = result["binary"]
    if binary is None:
        return None
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH",)}
    env.update(PYTHONUTF8="1")
    try:
        done = subprocess.run([str(binary)], cwd=result["work"], env=env, input=b"",
                              capture_output=True, timeout=120, preexec_fn=limit_memory)
    except subprocess.TimeoutExpired:
        return {"returncode": "timeout", "stdout": b""}
    return {"returncode": done.returncode, "stdout": done.stdout}


def first_difference(left, right):
    a = left.decode("utf-8", "replace").splitlines()
    b = right.decode("utf-8", "replace").splitlines()
    for index, (x, y) in enumerate(zip(a, b), 1):
        if x != y:
            return index, x, y
    if len(a) != len(b):
        index = min(len(a), len(b)) + 1
        return index, a[index - 1] if index <= len(a) else "<eof>", b[index - 1] if index <= len(b) else "<eof>"
    return None


def check(item, python, sdk, root):
    label, source = item
    work = Path(tempfile.mkdtemp(prefix="same-c-", dir=root))
    try:
        checkout = build(sys.executable, COMPILER, source, work / "checkout")
        installed = build(python, sdk / "ail_chatgpt.py", source, work / "installed")
        findings = []
        if checkout["returncode"] != installed["returncode"]:
            findings.append("build exit %d vs %d" % (checkout["returncode"], installed["returncode"]))
        if checkout["program_c"] != installed["program_c"]:
            if checkout["program_c"] is None or installed["program_c"] is None:
                findings.append("program.c missing in one build")
            else:
                difference = first_difference(checkout["program_c"], installed["program_c"])
                if difference:
                    findings.append("program.c line %d: %r vs %r" % difference)
                else:
                    findings.append("program.c bytes differ")
        left, right = run_binary(checkout), run_binary(installed)
        if left is None or right is None:
            if left is not right:
                findings.append("built program missing in one build")
        elif left["returncode"] != right["returncode"]:
            findings.append("program exit %r vs %r" % (left["returncode"], right["returncode"]))
        elif left["stdout"] != right["stdout"]:
            difference = first_difference(left["stdout"], right["stdout"])
            findings.append("program stdout differs: %r" % (difference,))
        return label, findings, checkout, installed
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main():
    items = programs()
    with tempfile.TemporaryDirectory(prefix="wheel-same-c-") as temporary:
        root = Path(temporary)
        python, sdk, wheel = make_wheel_venv(root)
        print("wheel:", wheel.name, "installed sdk:", sdk, flush=True)
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(check, item, python, sdk, root) for item in items]
            for future in concurrent.futures.as_completed(futures):
                results.append(future.result())
        matched = 0
        for label, findings, checkout, installed in sorted(results):
            if findings:
                print("DIFF %-28s %s" % (label, "; ".join(findings)), flush=True)
                if checkout["stderr"].strip() or installed["stderr"].strip():
                    print("  checkout stderr: %s" % checkout["stderr"].strip().splitlines()[-1:], flush=True)
                    print("  installed stderr: %s" % installed["stderr"].strip().splitlines()[-1:], flush=True)
            else:
                matched += 1
                print("ok   %s" % label, flush=True)
        print("%d/%d programs build the same C from the checkout and the installed wheel" % (matched, len(items)))
        return 0 if matched == len(items) else 1


if __name__ == "__main__":
    sys.exit(main())
