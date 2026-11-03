"""The `ail` command: run, build and check AIL programs with the SDK bundled in this wheel.

    ail run prog.py [args...]      compile to a temporary executable and run it
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
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

from . import __version__, project

SDK = Path(os.environ.get("AIL_SDK_DIR") or Path(__file__).resolve().parent / "sdk")   # AIL_SDK_DIR: a source checkout's AIL_CURRENT
C_COMPILERS = ("cc", "clang", "gcc")
EXE = ".exe" if os.name == "nt" else ""
BUILD_COMMANDS = ("compile", "compile-module", "compile-library", "compile-c")
PASS_THROUGH = BUILD_COMMANDS + ("api", "api-builtin", "context", "edit", "doctor", "integrity", "cache",
                                 "export-sdk")

SHORT_USAGE = """usage: ail <command> [options] [arguments]
Try 'ail --help' for the command list, or 'ail <command> --help' for one command."""

HELP = """usage: ail <command> [options] [arguments]

AIL compiles Python-syntax programs to standalone C executables.
Run `ail <command> --help` for the options of one command.

commands:
  run PROG.py [ARGS...]   compile to a temporary executable and run it; ARGS go to the program
  build PROG.py           compile to an executable (default output: PROG without .py)
  check PROG.py           type-check source without a C compiler
  new NAME                create a project directory (ail.toml and src/main.py)
  lsp                     run the language server on stdio (diagnostics and hover)
  compile PROG.py         compile to an executable (the SDK compile command)
  compile-module FILE     compile typed functions and data to a reusable object
  compile-library FILE    build a C-callable library with owned results and error returns
  compile-c FILE          compile trusted C functions to a typed reusable object
  api MODULE              print the typed API of a bundled module
  api-builtin [SYMBOL]    print intrinsic signatures or ownership contracts
  context PROG.py         read a function declaration and its call candidates
  edit PROG.py            replace function bodies in a new checked candidate
  doctor [--check]        report the Python, the C compiler and the SDK root
  integrity               verify the SDK files against MANIFEST.json
  cache stats|path|clear  inspect or clear the per-user build cache
  export-sdk -o DIR       copy the verified SDK to a new directory

project commands (no source file):
  run | build | check     use the nearest project (ail.toml or [tool.ail] in pyproject.toml);
                          build writes build/NAME

options for run and build:
  -o, --output PATH       write the executable to PATH (default: the source name without .py)
  --strict                build only on the typed path, listing every blocker and a rewrite
  --json                  with --strict, print blockers as machine-readable ail.strict/1 JSON
  --lib NAME              build @export functions as a C library (libNAME.so, libNAME.a, NAME.h)
  -I, --module-path DIR   add a module search directory (repeatable)
  --module FILE           add a source module to the build (repeatable)
  --object FILE           link an existing typed object (repeatable)
  --link LIB              link this C library as well (repeatable)
  --static                link the C library statically instead of dynamically
  --no-cache              do not read or write the build cache
  --syntax MODE           source syntax: auto (default) or python

experimental and debug options (run and build; may change):
  --debug                 build for gdb: -g -O0 and #line directives to the source
  --debug-dir DIR         keep native diagnostic reports and generated sources in DIR
  --target TRIPLE         cross-compile with zig cc for another OS/CPU
  --exact-int             use CPython's arbitrary-precision ints (about 20x slower)
  --separate              compile each typed source to an object, then link the objects
  --fe-cache              cache the generated C under ~/.cache/ail/fe
  --gpu                   build loops marked '# ail: gpu' as GPU kernels
  --freestanding          emit a libc-free C file or object and a header
  --m32                   with --freestanding: target 32-bit x86

global options:
  -h, --help              show this help and exit
  --version, -V           print the version and exit"""

RUN_HELP = """usage: ail run PROG.py [options] [ARGS...]

Compile PROG.py to a temporary executable and run it. The first word that is not an
option (or an option value) is the source file; everything after it goes to the program,
so program options do not need a `--`.

options:
  --strict                build only on the typed path, listing every blocker and a rewrite
  --json                  with --strict, print blockers as machine-readable ail.strict/1 JSON
  --lib NAME              build @export functions as a C library (libNAME.so, libNAME.a, NAME.h)
  -I, --module-path DIR   add a module search directory (repeatable)
  --module FILE           add a source module to the build (repeatable)
  --object FILE           link an existing typed object (repeatable)
  --link LIB              link this C library as well (repeatable)
  --static                link the C library statically instead of dynamically
  --no-cache              do not read or write the build cache
  --syntax MODE           source syntax: auto (default) or python
  -h, --help              show this help and exit

experimental and debug options (may change):
  --debug                 build for gdb: -g -O0 and #line directives to the source
  --debug-dir DIR         keep native diagnostic reports and generated sources in DIR
  --target TRIPLE         cross-compile with zig cc for another OS/CPU
  --exact-int             use CPython's arbitrary-precision ints (about 20x slower)
  --separate              compile each typed source to an object, then link the objects
  --fe-cache              cache the generated C under ~/.cache/ail/fe
  --gpu                   build loops marked '# ail: gpu' as GPU kernels
  --freestanding          emit a libc-free C file or object and a header
  --m32                   with --freestanding: target 32-bit x86"""

BUILD_HELP = """usage: ail build PROG.py [options]

Compile PROG.py to an executable. Without -o/--output the output is PROG.py without
.py. With no source file, build the project found from the current directory upwards
(ail.toml or [tool.ail] in pyproject.toml) and write build/NAME.

options:
  -o, --output PATH       write the executable to PATH (default: the source name without .py)
  --strict                build only on the typed path, listing every blocker and a rewrite
  --json                  with --strict, print blockers as machine-readable ail.strict/1 JSON
  --lib NAME              build @export functions as a C library (libNAME.so, libNAME.a, NAME.h)
  -I, --module-path DIR   add a module search directory (repeatable)
  --module FILE           add a source module to the build (repeatable)
  --object FILE           link an existing typed object (repeatable)
  --link LIB              link this C library as well (repeatable)
  --static                link the C library statically instead of dynamically
  --no-cache              do not read or write the build cache
  --syntax MODE           source syntax: auto (default) or python
  -h, --help              show this help and exit

experimental and debug options (may change):
  --debug                 build for gdb: -g -O0 and #line directives to the source
  --debug-dir DIR         keep native diagnostic reports and generated sources in DIR
  --target TRIPLE         cross-compile with zig cc for another OS/CPU
  --exact-int             use CPython's arbitrary-precision ints (about 20x slower)
  --separate              compile each typed source to an object, then link the objects
  --fe-cache              cache the generated C under ~/.cache/ail/fe
  --gpu                   build loops marked '# ail: gpu' as GPU kernels
  --freestanding          emit a libc-free C file or object and a header
  --m32                   with --freestanding: target 32-bit x86"""

NEW_HELP = """usage: ail new NAME

Create the project directory NAME with NAME/ail.toml and NAME/src/main.py.
The directory must not exist yet. Then `cd NAME` and run `ail run` or `ail build`.

  -h, --help              show this help and exit"""

LSP_HELP = """usage: ail lsp

Run the AIL language server on stdin/stdout, for an editor's LSP client
(diagnostics and hover).

  -h, --help              show this help and exit"""

COMMAND_HELP = {"run": RUN_HELP, "build": BUILD_HELP, "new": NEW_HELP, "lsp": LSP_HELP}


def _command_help(command):
    """The help text of one command; the SDK commands print their own --help when it is available."""
    return COMMAND_HELP.get(command)

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


def _split_source(argv):
    """(compiler options, source, program arguments). The first word that is not an option or an
    option value is the source file."""
    value_options = {"-o", "--output", "-I", "--module-path", "--module", "--object", "--syntax", "--target",
                     "--debug-dir", "--link", "--lib"}
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
    print("ail: no project found from %s (looked for ail.toml or [tool.ail] in pyproject.toml).\n"
          "Give a source file: ail %s prog.py\n"
          "Or create a project first: ail new NAME" % (Path.cwd(), command), file=sys.stderr)
    return 2


def _help_wanted(rest):
    return bool(rest) and rest[0] in ("-h", "--help")


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


def cmd_run(argv):
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


def _sdk_help(command):
    """The SDK command's own help, with the program name the user typed."""
    if (SDK / "ail_chatgpt.py").is_file():
        done = subprocess.run(_sdk_command(command, "--help"), env=_env(), capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        sys.stdout.write(done.stdout.replace("ail_chatgpt.py", "ail"))
        sys.stderr.write(done.stderr.replace("ail_chatgpt.py", "ail"))
        return done.returncode
    print("usage: ail %s [options]\n\nThe bundled SDK is missing at %s (broken installation; reinstall ailc)."
          % (command, SDK), file=sys.stderr)
    return 2


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print(SHORT_USAGE, file=sys.stderr)
        return 2
    if argv[0] in ("-h", "--help"):
        print(HELP)
        return 0
    if argv[0] == "help":
        if len(argv) == 1:
            print(HELP)
            return 0
        command = argv[1]
        if command in COMMAND_HELP:
            print(COMMAND_HELP[command])
            return 0
        if command == "check" or command in PASS_THROUGH:
            return _sdk_help(command)
        print("ail: unknown command %r\n\n%s" % (command, SHORT_USAGE), file=sys.stderr)
        return 2
    if argv[0] in ("--version", "-V", "version"):
        print("ailc %s" % __version__)
        return 0
    command, rest = argv[0], argv[1:]
    if command in COMMAND_HELP and _help_wanted(rest):
        print(COMMAND_HELP[command])
        return 0
    if not (SDK / "ail_chatgpt.py").is_file():
        print("ail: the bundled SDK is missing at %s (broken installation; reinstall ailc)" % SDK,
              file=sys.stderr)
        return 2
    if _help_wanted(rest) and (command == "check" or command in PASS_THROUGH):
        return _sdk_help(command)
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
    print("ail: unknown command %r\n\n%s" % (command, SHORT_USAGE), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
