"""`ail fmt --check`: does an existing formatter reformat these AIL sources?

AIL is Python syntax, so AIL writes no formatter of its own.  This module runs `ruff format` when
ruff is on `PATH`, else `black`, and asks only for an answer; it never writes a file (there is no
`--write` mode).  Neither formatter becomes a dependency of the package: without one the command
exits 2 and says how to install ruff.

    python3 -m ail_lang.fmt --check FILE...
    python3 -m ail_lang.fmt --check src/main.py lib/util.py

Exit status:

    0   every file is already formatted
    1   at least one file would change; the unified diff is on stdout
    2   no formatter on PATH (or the formatter itself failed)

`[fmt] line-length` in the nearest `ail.toml` (e.g. `line-length = 100`) is passed through as the
formatter's `--line-length`; without it the formatter's own default applies.
"""
import shutil
import subprocess
import sys
from pathlib import Path

MISSING = "ail fmt needs ruff or black on PATH: pip install ruff"
USAGE = "usage: ail fmt --check FILE..."


def find_formatter():
    """Return (name, command prefix) for ruff, else black, else (None, None)."""
    ruff = shutil.which("ruff")
    if ruff:
        return "ruff", [ruff, "format"]
    black = shutil.which("black")
    if black:
        return "black", [black]
    return None, None


def _line_length_from(text):
    """`line-length` (or `line_length`) from the `[fmt]` table of a TOML text, or None."""
    table = None
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            table = line[1:-1].strip()
            continue
        if table != "fmt":
            continue
        key, separator, value = line.partition("=")
        if not separator:
            continue
        if key.strip().strip("\"'").replace("_", "-") != "line-length":
            continue
        try:
            number = int(value.strip().strip("\"'"))
        except ValueError:
            continue
        if number > 0:
            return number
    return None


def line_length(path):
    """The `[fmt] line-length` of the nearest `ail.toml` above `path`, or None."""
    start = path if path.is_dir() else path.parent
    for directory in (start, *start.parents):
        config = directory / "ail.toml"
        if config.is_file():
            try:
                return _line_length_from(config.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                return None
    return None


def formatter_command(name, prefix, path, length):
    """The check-and-diff command for one file: stdout is a unified diff, the file is not written."""
    options = []
    if length is not None:
        options += ["--line-length", str(length)]
    if name == "ruff":
        return prefix + ["--check", "--diff"] + options + [str(path)]
    return prefix + ["--check", "--diff", "--color=false"] + options + [str(path)]


def check(paths):
    """Return 0 (all formatted), 1 (some would change, diffs printed) or 2 (error)."""
    name, prefix = find_formatter()
    if name is None:
        print(MISSING, file=sys.stderr)
        return 2
    would_change = False
    for path in paths:
        command = formatter_command(name, prefix, path, line_length(path))
        done = subprocess.run(command, capture_output=True, text=True)
        sys.stdout.write(done.stdout)
        if done.stderr.strip():
            sys.stderr.write(done.stderr)
        if done.returncode == 0:
            continue
        if done.returncode == 1:
            would_change = True
            continue
        print("ail fmt: %s failed on %s (exit %d)" % (name, path, done.returncode), file=sys.stderr)
        return 2
    return 1 if would_change else 0


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    check_mode = "--check" in args
    files = [argument for argument in args if argument != "--check"]
    if not check_mode or not files or any(argument.startswith("-") and argument != "-" for argument in files):
        print(USAGE, file=sys.stderr)
        return 2
    return check([Path(name) for name in files])


if __name__ == "__main__":
    sys.exit(main())
