#!/usr/bin/env python3
"""ffpkg0 census: build a small AIL program against 30 pinned pure-Python wheels.

    python3 -I -B lab/pkg/census.py [--cache DIR]

For every `name==version` line in packages.txt this script

1. downloads exactly one pure wheel (`pip download --no-deps --only-binary=:all:`),
2. unpacks it into a directory of its own (never on the interpreter's import path),
3. writes a short program that imports the package and calls one function,
4. builds it with `AIL_CURRENT/ail_chatgpt.py compile`, with the package's own
   wheel root (and, where the package requires one, the roots of its declared
   dependencies) on AIL_PATH, and runs the executable beside CPython's run of
   the same program (PYTHONPATH plays the part of AIL_PATH for the oracle),
5. classifies it as `built typed`, `built general`, `refused` (with the first
   refusal line), or `output differs`, and writes lab/pkg/RESULTS.md.

The downloaded source is never imported by this script; only the built program
and the CPython oracle read it.  Each package lives in its own empty directory.
A silent difference stops the run (the program and both outputs are recorded).
"""
import argparse
import hashlib
import html
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AIL = REPO / "AIL_CURRENT" / "ail_chatgpt.py"
PACKAGES = HERE / "packages.txt"
RESULTS = HERE / "RESULTS.md"
MEM_LIMIT = 1500000 * 1024          # the 1.5 GB address-space cap from the brief

# Required third-party imports of the probe (checked against CPython with only
# the package's own wheel on the path).  Optional imports such as tabulate's
# wcwidth and click's colorama are deliberately absent: the probe does not need
# them, and pulling in unrelated packages would mask the package's own blocker.
DEPENDS = {
    "python-dateutil": ("six",),
    "markdown-it-py": ("mdurl",),
}

PROGRAMS = {
    "tabulate": '''from tabulate import tabulate
rows = [["Alice", 24], ["Bob", 19]]
print(tabulate(rows, headers=["name", "age"]))
print(tabulate([[1, 2.5]], tablefmt="plain"))
''',
    "colorama": '''from colorama import Fore, Style
print(Fore.RED + "red" + Style.RESET_ALL)
print(Fore.GREEN + "ok" + Style.RESET_ALL)
''',
    "click": '''import click
print(click.style("hi", fg="green"))
print(click.unstyle("\\x1b[31mx\\x1b[0m"))
''',
    "toml": '''import toml
text = 'title = "x"\\n[owner]\\nname = "Alice"\\n'
data = toml.loads(text)
print(data["title"], data["owner"]["name"])
''',
    "six": '''import six
print(six.PY3)
print(six.int2byte(65))
''',
    "python-dateutil": '''from dateutil.parser import parse
print(parse("2024-02-29T12:34:56"))
print(parse("Jan 2, 2020"))
''',
    "idna": '''import idna
print(idna.encode("example.com"))
print(idna.decode("xn--bcher-kva.example"))
''',
    "wcwidth": '''from wcwidth import wcwidth, wcswidth
print(wcwidth("a"), wcwidth("界"), wcswidth("a界"))
''',
    "texttable": '''from texttable import Texttable
table = Texttable()
table.add_rows([["Name", "Age"], ["Alice", 24]])
print(table.draw())
''',
    "more-itertools": '''from more_itertools import chunked, flatten
print(list(chunked([1, 2, 3, 4, 5], 2)))
print(list(flatten([[1, 2], [3]])))
''',
    "packaging": '''from packaging.version import Version
print(Version("1.2.3") < Version("1.3"))
print(Version("2.0.0rc1").is_prerelease)
''',
    "pyparsing": '''import pyparsing as pp
word = pp.Word(pp.alphas)
print(word.parse_string("abc").as_list())
''',
    "tomli": '''import tomli
data = tomli.loads('a = 1\\n[b]\\nc = "x"\\n')
print(data)
''',
    "tomli-w": '''import tomli_w
print(tomli_w.dumps({"a": 1, "b": {"c": "x"}}))
''',
    "appdirs": '''import appdirs
print(appdirs.user_config_dir("myapp", "myorg"))
print(appdirs.user_cache_dir("myapp"))
''',
    "pytz": '''import pytz
from datetime import datetime
print(pytz.utc)
print(pytz.timezone("Europe/Paris").localize(datetime(2024, 6, 1, 12)).utcoffset())
''',
    "markdown-it-py": '''from markdown_it import MarkdownIt
md = MarkdownIt()
print(md.render("**bold** and *em*"))
''',
    "mdurl": '''import mdurl
print(mdurl.encode("a b"))
print(mdurl.decode("a%20b"))
''',
    "pyfiglet": '''import pyfiglet
print(pyfiglet.figlet_format("A", font="standard"))
''',
    "art": '''from art import text2art
print(text2art("A", font="standard"))
''',
    "humanize": '''import humanize
print(humanize.intcomma(1234567))
print(humanize.intword(1234567))
''',
    "pygments": '''from pygments.lexers.python import PythonLexer
tokens = list(PythonLexer().get_tokens("x = 1"))
print(len(tokens), tokens[0][1], tokens[1][1], tokens[2][1])
''',
    "rich": '''from rich.text import Text
text = Text("hello")
text.stylize("bold", 0, 5)
print(text.plain, len(text.spans))
''',
    "boltons": '''from boltons.iterutils import chunked
print(list(chunked([1, 2, 3, 4, 5], 2)))
''',
    "toolz": '''from toolz import merge
print(merge({1: 2}, {3: 4}))
''',
    "funcy": '''import funcy
print(funcy.chunks(2, [1, 2, 3, 4, 5]))
print(funcy.flatten([[1, 2], [3]]))
''',
    "semver": '''import semver
print(semver.Version.parse("1.2.3").bump_minor())
print(semver.compare("1.2.3", "1.2.4"))
''',
    "xmltodict": '''import xmltodict
print(xmltodict.parse("<root><a>1</a><b>x</b></root>"))
''',
    "defusedxml": '''from defusedxml import ElementTree as ET
root = ET.fromstring("<root><a>1</a></root>")
print(root.tag, root.find("a").text)
''',
    "json5": '''import json5
print(json5.loads("{a: 1, b: [2, 3]}"))
''',
}


def read_specs(path):
    specs = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, separator, version = line.partition("==")
        if not separator or not name or not version:
            raise SystemExit("%s:%d: expected name==version" % (path, number))
        specs.append((name, version))
    if len(specs) != 30:
        raise SystemExit("%s: expected 30 pinned packages, found %d" % (path, len(specs)))
    missing = [name for name, _ in specs if name not in PROGRAMS]
    if missing:
        raise SystemExit("no probe program for: %s" % ", ".join(missing))
    return specs


def safe_extract(wheel, destination):
    """Unpack a wheel below `destination`, refusing entries that escape it."""
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    with zipfile.ZipFile(wheel) as archive:
        for info in archive.infolist():
            target = (destination / info.filename).resolve()
            if target != root and root not in target.parents:
                raise RuntimeError("%s: wheel entry escapes its directory: %s" % (wheel, info.filename))
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise RuntimeError("%s: wheel contains a symbolic link: %s" % (wheel, info.filename))
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, open(target, "wb") as output:
                shutil.copyfileobj(source, output)


def download(name, version, cache):
    key = re.sub(r"[^A-Za-z0-9_.-]+", "_", "%s==%s" % (name, version))
    directory = cache / key
    wheels = sorted(directory.glob("*.whl"))
    if not wheels:
        directory.mkdir(parents=True, exist_ok=True)
        command = [sys.executable, "-m", "pip", "download", "--no-deps", "--only-binary=:all:",
                   "--dest", str(directory), "%s==%s" % (name, version)]
        done = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if done.returncode:
            raise RuntimeError("pip download failed for %s==%s:\n%s\n%s"
                               % (name, version, done.stdout, done.stderr))
        wheels = sorted(directory.glob("*.whl"))
    if len(wheels) != 1:
        raise RuntimeError("%s==%s: expected one wheel, found %s" % (name, version, wheels))
    wheel = wheels[0]
    if "none-any" not in wheel.name:
        raise RuntimeError("%s==%s: not a pure-Python wheel: %s" % (name, version, wheel.name))
    return wheel


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def limited_run(command, cwd, env, timeout):
    options = {}
    if os.name == "posix":
        def limits():
            import resource
            resource.setrlimit(resource.RLIMIT_AS, (MEM_LIMIT, MEM_LIMIT))
        options["preexec_fn"] = limits
    return subprocess.run(command, cwd=str(cwd), env=env, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout, **options)


def base_env():
    env = dict(os.environ)
    for key in ("AIL_PATH", "PYTHONPATH", "AIL_STRICT", "AIL_EXACT_INT", "AIL_UNIFIED_FORCE"):
        env.pop(key, None)
    env["AIL_NO_CACHE"] = "1"
    env["PYTHONUTF8"] = "1"
    return env


def first_refusal(stderr):
    for line in stderr.splitlines():
        text = line.strip()
        if not text or text.startswith("note:") or text.startswith("write instead:"):
            continue
        return text
    return "compile failed without a diagnostic"


def general_note(stderr):
    for line in stderr.splitlines():
        if "built on the general path" in line:
            return line.strip()
    return "built on the general path"


def dependency_prefix(reason, name, roots):
    """Say so when the first refusal comes from a required dependency, not the package."""
    for dependency in DEPENDS.get(name, ()):
        if str(roots[dependency]) in reason:
            return "from dependency %s: %s" % (dependency, reason)
    return reason


def strip_roots(text, roots, work=None):
    """Drop temporary prefixes so a refusal reads as package/module.py:line."""
    for root in roots.values():
        text = text.replace(str(root) + os.sep, "")
    if work is not None:
        text = text.replace(str(work) + os.sep, "")
    return text


def clean(text):
    text = text.replace("\r\n", "\n")
    return text if len(text) < 4000 else text[:4000] + "\n...[truncated]"


def cell(text):
    return html.escape(str(text), quote=False).replace("|", "&#124;").replace("\n", " ")


def code_cell(text):
    return "<code>%s</code>" % cell(text)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cache", type=Path, help="keep downloaded wheels here (default: a temporary directory)")
    parser.add_argument("--timeout", type=int, default=180, help="seconds for one AIL build (default: 180)")
    parser.add_argument("--keep-going", action="store_true",
                        help="continue after an output difference (the default stops, as the brief requires)")
    options = parser.parse_args(argv)

    specs = read_specs(PACKAGES)
    if not AIL.is_file():
        raise SystemExit("compiler not found: %s" % AIL)

    temporary = None
    if options.cache:
        cache = options.cache.resolve()
        cache.mkdir(parents=True, exist_ok=True)
    else:
        temporary = tempfile.TemporaryDirectory(prefix="ail-pkg-census-")
        cache = Path(temporary.name)

    work = cache / "work"
    programs = work / "programs"
    binaries = work / "bin"
    runs = work / "run"
    roots = work / "roots"
    for directory in (programs, binaries, runs, roots):
        directory.mkdir(parents=True, exist_ok=True)

    environment = base_env()
    environment["PYTHONPATH"] = ""
    rows, wheel_rows = [], []
    roots_by_name = {}
    started = time.time()

    print("downloading and unpacking %d wheels under %s" % (len(specs), cache), file=sys.stderr)
    for index, (name, version) in enumerate(specs, 1):
        wheel = download(name, version, cache)
        root = roots / re.sub(r"[^A-Za-z0-9_.-]+", "_", name)
        if root.is_dir():
            shutil.rmtree(root)
        safe_extract(wheel, root)
        roots_by_name[name] = root
        wheel_rows.append((name, version, wheel.name, digest(wheel)))
        print("  [%02d/%02d] %s==%s" % (index, len(specs), name, version), file=sys.stderr)

    for name, dependencies in DEPENDS.items():
        for dependency in dependencies:
            if dependency not in roots_by_name:
                raise SystemExit("%s depends on %s, which is not in packages.txt"
                                 % (name, dependency))

    stopped = None
    for index, (name, version) in enumerate(specs, 1):
        source = programs / ("%02d_%s.py" % (index, re.sub(r"[^A-Za-z0-9_.-]+", "_", name)))
        source.write_text(PROGRAMS[name], encoding="utf-8")
        binary = binaries / ("%02d_%s" % (index, re.sub(r"[^A-Za-z0-9_.-]+", "_", name)))
        if binary.exists():
            binary.unlink()
        run_dir = runs / ("%02d_%s" % (index, re.sub(r"[^A-Za-z0-9_.-]+", "_", name)))
        run_dir.mkdir(parents=True, exist_ok=True)
        search = os.pathsep.join(str(roots_by_name[part])
                                 for part in (name,) + DEPENDS.get(name, ()))
        build_env = dict(environment, AIL_PATH=search)
        oracle_env = dict(environment, PYTHONPATH=search)

        print("[%02d/%02d] %s==%s: building" % (index, len(specs), name, version), file=sys.stderr)
        started_one = time.time()
        try:
            built = limited_run([sys.executable, "-S", "-B", str(AIL), "compile",
                                 str(source), "-o", str(binary)],
                                run_dir, build_env, options.timeout)
        except subprocess.TimeoutExpired:
            rows.append(dict(name=name, version=version, result="refused",
                             reason="compile timed out after %d s" % options.timeout,
                             seconds=time.time() - started_one))
            continue
        seconds = time.time() - started_one

        if built.returncode != 0:
            reason = dependency_prefix(first_refusal(built.stderr), name, roots_by_name)
            reason = strip_roots(reason, roots_by_name, work)
            rows.append(dict(name=name, version=version, result="refused",
                             reason=reason, seconds=seconds))
            print("  refused: %s" % reason[:140], file=sys.stderr)
            continue

        result = "built general" if "built on the general path" in built.stderr else "built typed"
        note = general_note(built.stderr) if result == "built general" else "stdout and exit status match CPython"
        note = strip_roots(note, roots_by_name, work)

        try:
            oracle = limited_run([sys.executable, "-S", "-B", str(source)], run_dir, oracle_env, 60)
        except subprocess.TimeoutExpired:
            rows.append(dict(name=name, version=version, result="oracle error",
                             reason="CPython timed out after 60 s", seconds=seconds))
            continue
        if oracle.returncode != 0:
            rows.append(dict(name=name, version=version, result="oracle error",
                             reason="CPython exit %d: %s" % (oracle.returncode,
                                                            strip_roots(first_refusal(oracle.stderr),
                                                                        roots_by_name, work)),
                             seconds=seconds))
            print("  oracle failed", file=sys.stderr)
            continue

        try:
            ran = limited_run([str(binary)], run_dir, oracle_env, 60)
            run_code = ran.returncode
            run_out, run_err = ran.stdout, ran.stderr
        except subprocess.TimeoutExpired:
            run_code, run_out, run_err = 124, "", "AIL executable timed out after 60 s"

        if run_code != oracle.returncode or run_out != oracle.stdout:
            row = dict(name=name, version=version, result="output differs", seconds=seconds,
                       reason="AIL exit %d, CPython exit %d" % (run_code, oracle.returncode),
                       program=PROGRAMS[name], oracle_out=clean(oracle.stdout),
                       oracle_err=clean(strip_roots(oracle.stderr, roots_by_name, work)),
                       ail_out=clean(run_out), ail_err=clean(strip_roots(run_err, roots_by_name, work)),
                       oracle_code=oracle.returncode, ail_code=run_code)
            rows.append(row)
            stopped = name
            print("  OUTPUT DIFFERS: %s" % row["reason"], file=sys.stderr)
            if not options.keep_going:
                break
        else:
            if run_err.strip():
                note += "; stderr: %s" % run_err.strip().splitlines()[0]
            rows.append(dict(name=name, version=version, result=result, reason=note, seconds=seconds))
            print("  %s" % result, file=sys.stderr)

    elapsed = time.time() - started
    counts = {}
    for row in rows:
        counts[row["result"]] = counts.get(row["result"], 0) + 1

    try:
        base = subprocess.check_output(["git", "-C", str(REPO), "rev-parse", "HEAD"],
                                       text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        base = "unknown"

    lines = ["# PyPI pure-Python packages on AIL (ffpkg0 census)", "",
             "Generated by `python3 -I -B lab/pkg/census.py`; the package list is `lab/pkg/packages.txt`.",
             "",
             "- Base: `%s`" % base,
             "- Oracle: CPython %s (`python3 -S -B <program>` with `PYTHONPATH` set)" % sys.version.split()[0],
             "- Build: `python3 -S -B AIL_CURRENT/ail_chatgpt.py compile <program> -o <exe>`",
             "- Search: every wheel unpacked into its own directory; `AIL_PATH` has the package root and, "
             "where needed, its declared dependency roots (`python-dateutil` -> `six`, "
             "`markdown-it-py` -> `mdurl`); `-S` hides the machine's site-packages",
             "- Limits: 1.5 GB address space, 180 s per build, 60 s per run, one build at a time",
             "- Elapsed: %.1f s" % elapsed, "",
             "## Counts", ""]
    for label in ("built typed", "built general", "refused", "output differs", "oracle error"):
        if label in counts:
            lines.append("- **%s**: %d" % (label, counts[label]))
    lines.append("- **built (typed or general)**: %d / %d"
                 % (counts.get("built typed", 0) + counts.get("built general", 0), len(specs)))
    lines.append("- **classified**: %d / %d" % (len(rows), len(specs)))
    if stopped:
        lines.append("")
        lines.append("The run stopped at **%s** because its output differed from CPython (brief stop rule)." % stopped)
    lines += ["", "## Packages", "",
              "| # | package | version | result | first refusal or note | seconds |",
              "|---:|---|---|---|---|---:|---|"]
    for index, row in enumerate(rows, 1):
        lines.append("| %d | `%s` | %s | %s | %s | %.1f |"
                     % (index, row["name"], row["version"], row["result"],
                        code_cell(row["reason"]), row["seconds"]))
    if stopped:
        done_names = {row["name"] for row in rows}
        for index, (name, version) in enumerate(specs, 1):
            if name not in done_names:
                lines.append("| %d | `%s` | %s | not run | stopped after %s |  |"
                             % (index, name, version, stopped))
    lines += ["", "## Wheels", "",
              "| package | version | wheel | sha256 |", "|---|---|---|---|"]
    for name, version, wheel, sha in wheel_rows:
        lines.append("| `%s` | %s | `%s` | <code>%s</code> |" % (name, version, cell(wheel), sha))
    differences = [row for row in rows if row["result"] == "output differs"]
    if differences:
        lines += ["", "## Silent differences", ""]
        for row in differences:
            lines += ["### %s==%s" % (row["name"], row["version"]), "", "```python",
                      row["program"].rstrip("\n"), "```", "",
                      "CPython exit %d:" % row["oracle_code"], "```",
                      row["oracle_out"].rstrip("\n") or "(no stdout)", "```", "",
                      "AIL exit %d:" % row["ail_code"], "```",
                      row["ail_out"].rstrip("\n") or "(no stdout)", "```"]
            if row["oracle_err"].strip() or row["ail_err"].strip():
                lines += ["", "CPython stderr:", "```", row["oracle_err"].rstrip("\n") or "(empty)", "```",
                          "", "AIL stderr:", "```", row["ail_err"].rstrip("\n") or "(empty)", "```", ""]
    lines.append("")
    RESULTS.write_text("\n".join(lines), encoding="utf-8")
    print("wrote %s: %d/%d classified in %.1f s" % (RESULTS, len(rows), len(specs), elapsed),
          file=sys.stderr)

    if temporary is not None:
        temporary.cleanup()
    if any(row["result"] in ("output differs", "oracle error") for row in rows):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
