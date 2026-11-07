"""The `ail` command: run, build and check AIL programs with the SDK bundled in this wheel.

    ail run prog.py [args...]      compile to a temporary executable and run it
    ail run --diff [--python PATH] [--timeout SEC] [--json] prog.py [args...]
                                   run it natively and under CPython with the same input, and report any
                                   difference (docs/CLI.md)
    ail build prog.py -o prog      compile to an executable (ail_chatgpt.py compile)
    ail build --lib name prog.py [-o dir]
                                   build the @export functions as a C library: dir/libname.so, libname.a, name.h
    ail build --strict prog.py     the same, but refuse (listing every blocker) instead of falling back
                                   to the slow general path; `ail run --strict` and AIL_STRICT=1 too
    ail check prog.py              strict source/type check, no C compiler needed (ail_chatgpt.py check)
    ail new NAME                   create a project directory (ail.toml, src/main.py)
    ail build | run | check        with no source file: the project of the current directory (ail.toml or [tool.ail])
    ail build --debug              -g -O0 with #line directives back to the source, for gdb; stdout buffered at a crash is lost
    ail lsp                        language server on stdio (diagnostics and hover)

Every other SDK command (compile, compile-module, compile-library, compile-c, api, api-builtin,
context, edit, doctor, integrity, cache, export-sdk) is passed to ail_chatgpt.py unchanged. The
compiler sources live in the `sdk` directory beside this file; they are exactly the files the SDK
export (ail_sdk.export_sdk) selects, so `ail integrity` verifies them against MANIFEST.json.
"""
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from . import __version__, project

SDK = Path(os.environ.get("AIL_SDK_DIR") or Path(__file__).resolve().parent / "sdk")   # AIL_SDK_DIR: a source checkout's AIL_CURRENT
C_COMPILERS = ("cc", "clang", "gcc")
EXE = ".exe" if os.name == "nt" else ""
BUILD_COMMANDS = ("compile", "compile-module", "compile-library", "compile-c")
PASS_THROUGH = BUILD_COMMANDS + ("api", "api-builtin", "context", "edit", "doctor", "integrity", "cache",
                                 "export-sdk")

USAGE = """usage: ail <command> ...

  ail run prog.py [args...]     compile to a temporary executable and run it
  ail build prog.py [-o prog]   compile to an executable (default output: the file name without .py)
  ail check prog.py             strict source/type check (needs no C compiler)
  ail new NAME                  create a project: NAME/ail.toml and NAME/src/main.py
  ail build | run | check       no source file: the project found from the current directory upwards
                                (ail.toml, or [tool.ail] in pyproject.toml); the program is build/NAME
  ail build --debug             -g -O0, #line directives to the source, an uncaught exception names file:line
  ail lsp                       language server on stdio (diagnostics, hover)
  ail build --lib NAME prog.py [-o DIR]
                                build the @export functions as a C library (libNAME.so, libNAME.a, NAME.h)
  ail build --strict prog.py    build on the typed path or refuse, listing every blocker and a rewrite
                                (also `ail run --strict`, AIL_STRICT=1; add --json for a machine-readable list)
  ail run --diff prog.py        run natively and under CPython on the same input; `ail diff: agree`, or
                                DIFFER / loud stop by design / timeout (exit 3, 4, 124; docs/CLI.md)
  ail doctor [--check]          report the Python, the C compiler and the SDK root
  ail cache stats|path|clear    the per-user build cache
  ail --version

Also available, as in ail_chatgpt.py: """ + ", ".join(PASS_THROUGH[:-1]) + """.
Options before the source file (for example --syntax, -I DIR, --static, --no-cache) go to the compiler;
everything after the source file of `ail run` goes to the program.
"""

NO_COMPILER = """ail: no C compiler found.

AIL compiles programs to C, so `ail run` and `ail build` need one of: {tried}.
Looked for them on PATH (and for zig via $AIL_ZIG or PATH).

Install one, then run `ail doctor` to confirm:
  Debian/Ubuntu   sudo apt install gcc
  Fedora          sudo dnf install gcc
  macOS           xcode-select --install
  Any OS          pip install "ailc[zig]"   (brings a zig cc, about 50 MB)
  Windows         or install Zig (https://ziglang.org/download/) or MinGW-w64 and put it on PATH
You can also point AIL at a compiler explicitly: set PIPE_CC=/path/to/cc (or AIL_ZIG=/path/to/zig).
`ail check` does not need a C compiler."""


# ---------------------------------------------------------------- C compiler and cache

def _zig():
    configured = os.environ.get("AIL_ZIG")
    if configured:
        return shutil.which(configured) or (configured if Path(configured).is_file() else None)
    found = shutil.which("zig")
    if found:
        return found
    # `pip install ailc[zig]` brings the ziglang wheel, which carries a zig binary
    try:
        import importlib.util
        spec = importlib.util.find_spec("ziglang")
        for directory in (spec.submodule_search_locations or []) if spec else []:
            candidate = Path(directory) / ("zig.exe" if os.name == "nt" else "zig")
            if candidate.is_file():
                return str(candidate)
    except (ImportError, ValueError):
        pass
    return None


def cache_root():
    """The build cache directory: $AIL_CACHE, else one directory per user."""
    configured = os.environ.get("AIL_CACHE")
    if configured:
        return Path(configured).expanduser()
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "ail" / "cache"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "ail"
    xdg = os.environ.get("XDG_CACHE_HOME")
    return (Path(xdg) if xdg else Path.home() / ".cache") / "ail"


def prepare_cache(env):
    """Point the build at a private per-user cache directory (owned by this user, not group/other
    writable). The directory is the compiler's trust root for cached executables, so one that another
    user owns is not used: the cache is switched off for that run."""
    try:
        root = cache_root()
        root.mkdir(parents=True, exist_ok=True)
        if os.name == "posix":
            info = root.stat()
            if info.st_uid != os.geteuid():
                raise OSError("owned by another user: %s" % root)
            if info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
                root.chmod(0o700)
        env["AIL_CACHE"] = str(root)
    except (OSError, RuntimeError) as error:
        print("ail: build cache disabled (%s)" % error, file=sys.stderr)
        env["AIL_NO_CACHE"] = "1"


def find_c_compiler(env):
    """Return (compiler, note). compiler is None when nothing usable exists; env gets PIPE_CC when
    zig has to stand in. A $PIPE_CC the user set is respected (and must resolve)."""
    configured = env.get("PIPE_CC")
    if configured:
        found = shutil.which(configured)
        return (found, "PIPE_CC") if found else (None, "PIPE_CC=%s does not resolve" % configured)
    for name in C_COMPILERS:
        found = shutil.which(name, path=env.get("PATH"))
        if found:
            return found, name
    zig = _zig()
    if zig:
        directory = cache_root() / "bin"
        try:
            directory.mkdir(parents=True, exist_ok=True)
            if os.name == "nt":
                wrapper, text = directory / "zigcc.cmd", '@"%s" cc %%*\r\n' % zig
            else:
                wrapper, text = directory / "zigcc", '#!/bin/sh\nexec "%s" cc "$@"\n' % zig
            if not wrapper.is_file() or wrapper.read_text(encoding="utf-8") != text:
                wrapper.write_text(text, encoding="utf-8")
                wrapper.chmod(0o755)
        except OSError as error:
            return None, "cannot write the zig cc wrapper: %s" % error
        env["PIPE_CC"] = str(wrapper)
        return str(wrapper), "zig cc"
    return None, ""


def require_compiler(env):
    compiler, note = find_c_compiler(env)
    if compiler:
        return compiler
    if note:
        print("ail: %s" % note, file=sys.stderr)
    else:
        print(NO_COMPILER.format(tried=", ".join(C_COMPILERS + ("zig cc",))), file=sys.stderr)
    return None


# ---------------------------------------------------------------- commands

def _sdk_command(*args):
    return [sys.executable, "-X", "utf8", "-B", str(SDK / "ail_chatgpt.py"), *map(str, args)]


# Compiler options that take a value, so the following word is not the source file.
_VALUE_OPTIONS = {"-o", "--output", "-I", "--module-path", "--module", "--object", "--syntax", "--target",
                  "--debug-dir", "--link", "--lib"}


def _source_index(argv, value_options):
    """The index of the first word that is not an option or an option value (len(argv) when there is
    none); a `--` ends the options, so the word after it is the source."""
    index = 0
    while index < len(argv):
        word = argv[index]
        if word == "--":
            return index + 1
        if word in value_options:
            index += 2
            continue
        if word.startswith("-") and word != "-":
            index += 1
            continue
        return index
    return len(argv)


def _split_source(argv):
    """(compiler options, source, program arguments). The first word that is not an option or an
    option value is the source file."""
    value_options = _VALUE_OPTIONS
    index = 0
    while index < len(argv):
        word = argv[index]
        if word == "--":
            index += 1
            break
        if word in value_options:
            index += 2
            continue
        if word.startswith("-") and word != "-":
            index += 1
            continue
        return argv[:index], word, argv[index + 1:]
    return argv[:index], None, argv[index:]


def _env():
    env = dict(os.environ)
    env.setdefault("PYTHONUTF8", "1")
    return env


def _project():
    """The project of the current directory, None when there is none; a broken config is reported."""
    try:
        return project.find(Path.cwd())
    except project.ProjectError as error:
        print("ail: %s" % error, file=sys.stderr)
        raise SystemExit(2)


def _no_project(command):
    print("usage: ail %s prog.py ...   (or run it inside a project: ail.toml or [tool.ail] in pyproject.toml; "
          "`ail new NAME` creates one)" % command, file=sys.stderr)
    return 2


def cmd_check(argv):
    options, source, rest = _split_source(argv)
    if source is None:
        found = _project()
        if found is None:
            return _no_project("check")
        return subprocess.call(_sdk_command("check", *found.compiler_options(), *options, found.entry), env=_env())
    return subprocess.call(_sdk_command("check", *argv), env=_env())


def _run_compiler(options, source, rest, env, debug, quiet=False):
    """Run `compile`. quiet drops its JSON result line (a project build prints its own). Under --debug a
    general-path note is followed by what the debug build of it lacks."""
    command = _sdk_command("compile", *options, source, *rest)
    if not debug and not quiet:
        return subprocess.call(command, env=env)
    built = subprocess.run(command, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if not quiet or built.returncode:
        sys.stdout.write(built.stdout)
    sys.stderr.write(built.stderr)
    if debug and built.returncode == 0 and "built on the general path" in built.stderr:
        print("ail: --debug: this program runs on the general path: gdb maps its C to source lines, but an "
              "uncaught exception does not name the statement (fix the note above, or use strict = true to be "
              "told at build time)", file=sys.stderr)
    return built.returncode


def cmd_build(argv):
    options, source, rest = _split_source(argv)
    debug = "--debug" in options
    env = _env()
    if source is None:
        found = _project()
        if found is None:
            return _no_project("build")
        explicit = "-o" in options or "--output" in options
        wanted = None if explicit else found.output.with_name(found.name + ("-debug" if debug else ""))
        if not require_compiler(env):
            return 2
        prepare_cache(env)
        if wanted is None:
            return _run_compiler(found.build_options() + options, found.entry, rest, env, debug)
        wanted.parent.mkdir(parents=True, exist_ok=True)
        # the compiler refuses an existing output, so build beside it and move the result over the old one
        with tempfile.TemporaryDirectory(prefix=".ail-build-", dir=str(wanted.parent)) as directory:
            target = Path(directory) / "program"
            code = _run_compiler(found.build_options() + options + ["-o", str(target)], found.entry, rest, env,
                                 debug, quiet=True)
            if code == 0:
                built = target if target.is_file() else Path(str(target) + EXE)
                if not built.is_file():
                    print("ail: the compiler reported success but produced no executable", file=sys.stderr)
                    return 2
                os.replace(built, str(wanted) + (EXE if built != target else ""))
                print("ail: built %s" % wanted)
        return code
    if "-o" not in options and "--output" not in options:
        #  writes lib<NAME>.so, lib<NAME>.a and <NAME>.h into a directory (default: here)
        options = options + ["-o", "." if "--lib" in options else str(Path(source).with_suffix(""))]
    if not require_compiler(env):
        return 2
    prepare_cache(env)
    return _run_compiler(options, source, rest, env, debug)


# ---------------------------------------------------------------- ail run --diff

# AIL's documented loud stops: a fixed-width or otherwise not-reproducible answer ends the program with
# a named error where CPython keeps going. `ail run --diff` reports these as "loud stop by design"
# instead of a difference. `stage` says where the message is read from: the native program's own stderr
# ("run") or the compiler's stderr when it refused the program ("build"). Sources:
# docs/LIMITATIONS.md sections 1 and 2, docs/MIGRATING.md sections 13 and 14, the "wording the
# general-path runtime prints for a limit, and the uncatchable runtime error.
LOUD_STOPS = (
    ("OverflowError: integer overflow in", "run", "int64 overflow: ints are 64-bit; --exact-int gives exact ints"),
    ("negative exponent on an integer", "run", "a negative exponent on an integer (CPython gives a float)"),
    ("re: the group did not take part in the match", "run",
     "a regex group that did not take part in the match"),
    ("a negative number raised to a fractional power", "run",
     "a negative number raised to a fractional power (complex)"),
    ("NaN used as a dict/set key", "run", "a NaN used as a dict or set key"),
    ("NaN used with 'in'", "run", "a NaN searched with `in`"),
    ("NaN used with list.count", "run", "a NaN searched in a list"),
    ("NaN searched with", "run", "a NaN searched (CPython only matches the same object)"),
    ("AIL internal error: ", "run", "an uncatchable AIL runtime error"),
    ("AIL limit: ", "run", "an AIL runtime limit (the CPython answer cannot be reproduced)"),
    ("ASCII-only in this runtime", "run", "a non-ASCII code point in an ASCII-only text method"),
    ("not in the subset", "build", "a construct AIL does not build (docs/LIMITATIONS.md)"),
    ("constant expression out of range", "build",
     "an int64 constant out of range (docs/LIMITATIONS.md section 1)"),
    ("int64 literal out of range", "build",
     "an int64 constant out of range (docs/LIMITATIONS.md section 1)"),
)

DIFF_EXIT_DIFFER = 3
DIFF_EXIT_LOUD = 4
DIFF_EXIT_TIMEOUT = 124

DIFF_VALUE_OPTIONS = ("--python", "--timeout")
# An uncaught exception on the last stderr line: "ValueError: ..." or "json.JSONDecodeError: ...".
# Only a Python exception class is accepted, so a compiler diagnostic such as "prog.py:1:1: ..." is not.
_EXCEPTION_LINE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*"
                             r"(?:Error|Exception|Exit|Interrupt|Warning|Iteration))\s*:")


def _split_diff(argv):
    """(settings, argv) for `ail run --diff`; (None, argv) when --diff is not before the source file.
    Only the options before the source are examined, so `ail run prog.py --diff` still hands --diff to
    the program, and `ail run` without --diff is left byte-for-byte alone."""
    options_end = _source_index(argv, _VALUE_OPTIONS | set(DIFF_VALUE_OPTIONS))
    settings = {"python": sys.executable or "python3", "timeout": 60.0, "json": False}
    seen, kept, index = False, [], 0
    while index < options_end:
        word = argv[index]
        name, equal, inline = word.partition("=")
        if word == "--diff":
            seen = True
            index += 1
        elif word == "--json":
            settings["json"] = True
            index += 1
        elif name in DIFF_VALUE_OPTIONS:
            if equal:
                value, step = inline, 1
            elif index + 1 < options_end:
                value, step = argv[index + 1], 2
            else:
                raise ValueError("%s needs a value" % name)
            if name == "--python":
                settings["python"] = value
            else:
                try:
                    settings["timeout"] = float(value)
                except ValueError:
                    raise ValueError("--timeout needs a number of seconds, not %r" % value)
                if not settings["timeout"] > 0:
                    raise ValueError("--timeout needs a positive number of seconds")
            index += step
        elif word in _VALUE_OPTIONS and index + 1 < options_end:
            # A compiler option and its value both go to the build, or `-I .` would leave the build
            # with a dangling option and no source.
            kept.extend((word, argv[index + 1]))
            index += 2
        else:
            kept.append(word)
            index += 1
    if not seen:
        return None, argv
    return settings, kept + argv[options_end:]


def _diff_text(value):
    """A value for the report: UTF-8 with escapes, at most 200 characters, no raw CR or newline."""
    shown = value.decode("utf-8", "backslashreplace") if isinstance(value, bytes) else str(value)
    shown = shown.replace("\r", "\\r")
    return shown if len(shown) <= 200 else shown[:200] + "..."


def _diff_stdout_line(left, right):
    """(1-based line number, native line, cpython line) of the first differing stdout line, else None.
    A side that has no such line (one output is a prefix of the other) says so instead of quoting an
    empty string."""
    absent = object()
    native_lines, cpython_lines = left.split(b"\n"), right.split(b"\n")
    for number in range(max(len(native_lines), len(cpython_lines))):
        a = native_lines[number] if number < len(native_lines) else absent
        b = cpython_lines[number] if number < len(cpython_lines) else absent
        if a != b:
            return (number + 1,
                    "<no such line>" if a is absent else _diff_text(a),
                    "<no such line>" if b is absent else _diff_text(b))
    return None


def _exception_name(stderr, code):
    """The uncaught exception's type name from the last non-empty stderr line, or None. Only a failed
    run has one, so a warning on a successful run is never mistaken for an exception."""
    if not code:
        return None
    for line in reversed(stderr.decode("utf-8", "replace").splitlines()):
        line = line.strip()
        if line:
            match = _EXCEPTION_LINE.match(line)
            return match.group(1) if match else None
    return None


def _loud_stop(stderr, stage):
    """The recognised loud-stop line in this stderr (of this stage), or None."""
    for line in stderr.decode("utf-8", "replace").splitlines():
        line = line.strip()
        if line and any(marker in line for marker, where, _label in LOUD_STOPS if where == stage):
            return _diff_text(line)
    return None


def _diff_run(command, cwd, env, stdin_path, timeout, live):
    """Run `command`; (exit code, stdout, stderr, timed_out, seconds). `live` streams the child's
    stdout and stderr to ours as they arrive (as `ail run` shows them); otherwise they are captured.
    stdin_path None means the child inherits our stdin. A child killed by a signal reports
    128 + the signal, as `ail run` does."""
    started = time.monotonic()
    feed = open(stdin_path, "rb") if stdin_path else None
    try:
        if not live:
            try:
                done = subprocess.run(command, cwd=cwd, env=env, stdin=feed, capture_output=True, timeout=timeout)
                code = done.returncode
                return (code if code >= 0 else 128 - code, done.stdout, done.stderr, False,
                        time.monotonic() - started)
            except subprocess.TimeoutExpired as expired:
                return (DIFF_EXIT_TIMEOUT, expired.stdout or b"", expired.stderr or b"", True,
                        time.monotonic() - started)
        proc = subprocess.Popen(command, cwd=cwd, env=env, stdin=feed,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        collected = {proc.stdout: [], proc.stderr: []}

        def pump(stream, sink, store):
            binary = getattr(sink, "buffer", None)
            while True:
                chunk = stream.read(65536)
                if not chunk:
                    break
                store.append(chunk)
                try:
                    if binary is not None:
                        binary.write(chunk)
                        binary.flush()
                    else:
                        sink.write(chunk.decode("utf-8", "replace"))
                        sink.flush()
                except (BrokenPipeError, ValueError):
                    pass

        threads = [threading.Thread(target=pump, args=(stream, sink, collected[stream]), daemon=True)
                   for stream, sink in ((proc.stdout, sys.stdout), (proc.stderr, sys.stderr))]
        for thread in threads:
            thread.start()
        timed_out = False
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            proc.kill()
            proc.wait()
        for thread in threads:
            thread.join(timeout=10)
        code = proc.returncode
        return (DIFF_EXIT_TIMEOUT if timed_out else (code if code >= 0 else 128 - code),
                b"".join(collected[proc.stdout]), b"".join(collected[proc.stderr]), timed_out,
                time.monotonic() - started)
    finally:
        if feed is not None:
            feed.close()


def _diff_verdict(native_code, native_out, native_err, cpython_code, cpython_out, cpython_err):
    """(kind, outcome text, line, native value, cpython value) for one pair of runs. The order
    matters: a native loud stop truncates stdout, so it is recognised before a stdout difference."""
    if native_code and cpython_code == 0:
        reason = _loud_stop(native_err, "run")
        if reason:
            return "loud stop by design", "loud stop by design: %s" % reason, None, reason, None
    differing = _diff_stdout_line(native_out, cpython_out)
    if differing:
        number, left, right = differing
        return ("differ", "DIFFER: stdout line %d: native %r, cpython %r" % (number, left, right),
                number, left, right)
    native_exc = _exception_name(native_err, native_code)
    cpython_exc = _exception_name(cpython_err, cpython_code)
    if native_exc != cpython_exc:
        return ("differ", "DIFFER: exception %s vs %s" % (native_exc or "none", cpython_exc or "none"), None,
                native_exc, cpython_exc)
    if native_code != cpython_code:
        return ("differ", "DIFFER: exit code %d vs %d" % (native_code, cpython_code), None,
                native_code, cpython_code)
    return "agree", "agree", None, None, None


def _diff_report(settings, kind, outcome, line, native_value, cpython_value, exit_codes, seconds,
                 native_stdout=b""):
    """Print the one report line (`ail diff:` on stderr, or one JSON object on stdout under --json)
    and give the exit code: the program's own on agreement, else 3, 4 or 124. `kind` is the JSON
    outcome ("agree", "differ", "loud stop by design", "timeout: native" / "timeout: cpython")."""
    if settings["json"]:
        sys.stdout.flush()
        if native_stdout and not native_stdout.endswith(b"\n"):
            sys.stdout.write("\n")        # keep the JSON on a line of its own after the program's output
        print(json.dumps({"outcome": kind, "line": line, "native": native_value,
                          "cpython": cpython_value, "exit": list(exit_codes),
                          "seconds": [round(one, 3) for one in seconds]}, ensure_ascii=False))
    else:
        print("ail diff: %s" % outcome, file=sys.stderr)
    if kind == "agree":
        return exit_codes[0]
    if kind == "differ":
        return DIFF_EXIT_DIFFER
    if kind == "loud stop by design":
        return DIFF_EXIT_LOUD
    return DIFF_EXIT_TIMEOUT


def _cmd_run_diff(argv, settings):
    """`ail run --diff`: build as `ail run` does, then run the program natively and under CPython with
    the same stdin, cwd, arguments, environment and timeout, and report any difference (docs/CLI.md)."""
    options, source, program_args = _split_source(argv)
    env = _env()
    if source is None:
        found = _project()
        if found is None:
            return _no_project("run")
        options, source = found.build_options() + options, str(found.entry)
    python = settings["python"]
    if os.sep in python or (os.altsep and os.altsep in python):
        if not (Path(python).is_file() and os.access(python, os.X_OK)):
            print("ail: --python %s: not an executable file" % python, file=sys.stderr)
            return 2
    else:
        found_python = shutil.which(python)
        if found_python is None:
            print("ail: --python %s: not found on PATH" % python, file=sys.stderr)
            return 2
        python = found_python
    if not require_compiler(env):
        return 2
    prepare_cache(env)
    timeout = settings["timeout"]
    cwd = os.getcwd()
    # Read stdin once and hand the very same bytes to both runs. An interactive stdin is left alone,
    # so a program that prompts is not robbed of its terminal.
    stdin_path, stdin_temp = None, None
    if not sys.stdin.isatty():
        stdin_temp = tempfile.NamedTemporaryFile(prefix="ail-diff-stdin-", delete=False)
        try:
            try:
                stdin_temp.write(sys.stdin.buffer.read())
            except (AttributeError, OSError):
                pass
        finally:
            stdin_temp.close()
        stdin_path = stdin_temp.name
    # Both runs get the same environment, inherited as it is: the compile env adds PYTHONUTF8, which
    # is the compiler's business and would change what CPython does with text.
    run_env = dict(os.environ)
    cpython_command = [python, source, *program_args]
    try:
        with tempfile.TemporaryDirectory(prefix="ail-run-") as directory:
            target = Path(directory) / "prog"
            built = subprocess.run(_sdk_command("compile", *options, source, "-o", target),
                                   env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
            sys.stderr.write(built.stderr)
            executable = target if target.is_file() else Path(str(target) + EXE)
            if built.returncode:
                return _diff_build_failed(settings, built, cpython_command, cwd, run_env, stdin_path, timeout)
            if not executable.is_file():
                print("ail: the compiler reported success but produced no executable", file=sys.stderr)
                return 2
            native_code, native_out, native_err, native_timeout, native_seconds = _diff_run(
                [str(executable), *program_args], cwd, run_env, stdin_path, timeout, live=True)
            if native_timeout:
                return _diff_report(settings, "timeout: native", "timeout: native", None, "timeout", None,
                                    (DIFF_EXIT_TIMEOUT, None), (native_seconds, 0.0),
                                    native_stdout=native_out)
            cpython_code, cpython_out, cpython_err, cpython_timeout, cpython_seconds = _diff_run(
                cpython_command, cwd, run_env, stdin_path, timeout, live=False)
            if cpython_timeout:
                return _diff_report(settings, "timeout: cpython", "timeout: cpython", None, None, "timeout",
                                    (native_code, DIFF_EXIT_TIMEOUT), (native_seconds, cpython_seconds),
                                    native_stdout=native_out)
            verdict = _diff_verdict(native_code, native_out, native_err,
                                    cpython_code, cpython_out, cpython_err)
            return _diff_report(settings, *verdict, exit_codes=(native_code, cpython_code),
                                seconds=(native_seconds, cpython_seconds), native_stdout=native_out)
    finally:
        if stdin_temp is not None:
            try:
                os.unlink(stdin_temp.name)
            except OSError:
                pass


def _diff_build_failed(settings, built, cpython_command, cwd, run_env, stdin_path, timeout):
    """No native program exists because the build stopped. When CPython still runs the program, that
    is AIL's own loud stop by design (a refusal or a compile-time int64 refusal). When CPython fails
    too, there is nothing to compare but the build's own stop, which is reported as such (a bare
    "exit code A vs B" would suggest a native program ran and exited A, which is not true)."""
    code, out, err, timed_out, seconds = _diff_run(cpython_command, cwd, run_env, stdin_path, timeout, live=False)
    first = (built.stderr.strip().splitlines() or ["the build stopped"])[0].strip()
    if timed_out:
        return _diff_report(settings, "timeout: cpython", "timeout: cpython", None, None, "timeout",
                            (built.returncode, DIFF_EXIT_TIMEOUT), (0.0, seconds))
    # A recognised refusal means no native program can exist for any input: it is AIL's own limit,
    # whether or not CPython happens to fail on this particular case too.
    reason = _loud_stop(built.stderr.encode("utf-8", "replace"), "build")
    if reason is None and code == 0:
        reason = _diff_text(first)
    if reason is not None:
        return _diff_report(settings, "loud stop by design", "loud stop by design: %s" % reason, None,
                            reason, None, (built.returncode, code), (0.0, seconds))
    quote = _diff_text(first)
    return _diff_report(settings, "differ", "DIFFER: no native program, the build stopped (exit %d) where "
                        "CPython exited %d: %s" % (built.returncode, code, quote), None,
                        "build stopped: %s" % quote, code, (built.returncode, code), (0.0, seconds))


def cmd_run(argv):
    try:
        settings, argv = _split_diff(argv)
    except ValueError as error:
        print("ail: %s" % error, file=sys.stderr)
        return 2
    if settings is not None:
        return _cmd_run_diff(argv, settings)
    options, source, program_args = _split_source(argv)
    env = _env()
    if source is None:
        found = _project()
        if found is None:
            return _no_project("run")
        options, source = found.build_options() + options, str(found.entry)
    if not require_compiler(env):
        return 2
    prepare_cache(env)
    with tempfile.TemporaryDirectory(prefix="ail-run-") as directory:
        target = Path(directory) / "prog"
        built = subprocess.run(_sdk_command("compile", *options, source, "-o", target),
                               env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
        sys.stderr.write(built.stderr)
        if built.returncode:
            if "--json" in options and built.stdout:      # `--strict --json`: the blocker list is on stdout
                sys.stdout.write(built.stdout)
            return built.returncode
        executable = target if target.is_file() else Path(str(target) + EXE)
        if not executable.is_file():
            print("ail: the compiler reported success but produced no executable", file=sys.stderr)
            return 2
        try:
            code = subprocess.call([str(executable), *program_args])
        except KeyboardInterrupt:
            return 130
    return 128 - code if code < 0 else code


def cmd_new(argv):
    if len(argv) != 1 or argv[0].startswith("-"):
        print("usage: ail new NAME", file=sys.stderr)
        return 2
    try:
        directory = project.scaffold(argv[0])
    except project.ProjectError as error:
        print("ail: %s" % error, file=sys.stderr)
        return 2
    print("ail: created %s\n  cd %s && ail run     # builds and runs src/main.py\n  ail build          # writes build/%s"
          % (directory, argv[0], directory.resolve().name))
    return 0


def cmd_lsp(argv):
    from . import lsp
    return lsp.serve()


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(USAGE)
        return 0 if argv else 2
    command, rest = argv[0], argv[1:]
    if command in ("--version", "-V", "version"):
        print("ailc %s" % __version__)
        return 0
    if not (SDK / "ail_chatgpt.py").is_file():
        print("ail: the bundled SDK is missing at %s (broken installation; reinstall ailc)" % SDK,
              file=sys.stderr)
        return 2
    try:
        if command == "run":
            return cmd_run(rest)
        if command == "build":
            return cmd_build(rest)
        if command == "check":
            return cmd_check(rest)
        if command == "new":
            return cmd_new(rest)
        if command == "lsp":
            return cmd_lsp(rest)
        if command in PASS_THROUGH:
            env = _env()
            if command in BUILD_COMMANDS:
                if not require_compiler(env):
                    return 2
            if command in BUILD_COMMANDS + ("cache",):
                prepare_cache(env)
            return subprocess.call(_sdk_command(command, *rest), env=env)
    except KeyboardInterrupt:
        return 130
    print("ail: unknown command %r\n\n%s" % (command, USAGE), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
