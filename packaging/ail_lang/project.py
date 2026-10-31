"""AIL projects: `ail.toml` (or `[tool.ail]` in pyproject.toml), `ail new`, and the no-argument `ail build`.

    # ail.toml
    name = "hello"              # the executable's name (default: the directory name)
    entry = "src/main.py"       # the entry module (required); .py or .ail
    link = ["z", "m"]           # C libraries to link, as -lz -lm (default: none)
    strict = false              # true: build with --strict (typed path only; every blocker is listed with a rewrite)
    module_path = ["src"]       # extra module directories, like -I (default: none)

The same keys under `[tool.ail]` in pyproject.toml work too; ail.toml wins when both exist. The project
root is the nearest directory (from the given one upwards) that holds either file with those keys.
Unknown keys and wrong types are refused by name, so a typo cannot silently change a build.
Standard library only (tomllib on Python 3.11+, a small reader for the same subset on 3.10).
"""
import json
import re
from pathlib import Path

CONFIG_NAMES = ("ail.toml", "pyproject.toml")
KEYS = {"name": str, "entry": str, "link": list, "strict": bool, "module_path": list}
NAME_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_-]*\Z")
LIBRARY_PATTERN = re.compile(r"[A-Za-z0-9_.+-]+\Z")
BUILD_DIRECTORY = "build"

MAIN_TEMPLATE = '''def main() -> None:
    print("hello from {name}")


if __name__ == "__main__":
    main()
'''
CONFIG_TEMPLATE = '''# AIL project. `ail build` builds `entry`, `ail run` builds and runs it, `ail check` type-checks it.
name = "{name}"
entry = "src/main.py"
link = []             # C libraries to link, for example ["z"]
strict = false        # true: refuse a program that would run on the slow general path
module_path = []      # extra module directories (the entry's own directory is always searched)
'''


class ProjectError(Exception):
    pass


class Project:
    def __init__(self, root, config_file, name, entry, link, strict, module_path):
        self.root, self.config_file, self.name, self.entry = root, config_file, name, entry
        self.link, self.strict, self.module_path = link, strict, module_path

    @property
    def output(self):
        return self.root / BUILD_DIRECTORY / self.name

    def compiler_options(self):
        """Options for `ail_chatgpt.py compile` / `check` that the project declares."""
        options = []
        for directory in self.module_path:
            options += ["-I", str(directory)]
        return options

    def build_options(self):
        options = self.compiler_options()
        for library in self.link:
            options += ["--link", library]
        if self.strict:
            options.append("--strict")      # every blocker with its rewrite (ail.strict/1), exit 3, nothing built
        return options


# ---------------------------------------------------------------- TOML

def _strip_comment(line):
    quote = None
    for index, char in enumerate(line):
        if quote:
            if char == quote and line[index - 1] != "\\":
                quote = None
        elif char in "\"'":
            quote = char
        elif char == "#":
            return line[:index]
    return line


def _value(text, where):
    text = text.strip()
    text = re.sub(r"'([^']*)'", lambda found: json.dumps(found.group(1)), text)
    text = re.sub(r",\s*\]", "]", text)
    try:
        return json.loads(text)
    except ValueError:
        raise ProjectError("%s: cannot read the value %r" % (where, text)) from None


def _read_toml_subset(text, where):
    """Tables, `key = value` with strings, booleans, integers and (multi-line) arrays of those: all that
    ail.toml and [tool.ail] use. Python 3.10 has no tomllib."""
    result, table, pending = {}, None, None
    table = result
    for number, raw in enumerate(text.splitlines(), 1):
        line = _strip_comment(raw).strip()
        if pending is not None:
            pending[1].append(line)
            joined = " ".join(pending[1])
            if joined.count("[") <= joined.count("]"):
                pending[0][pending[2]] = _value(joined, "%s:%d" % (where, pending[3]))
                pending = None
            continue
        if not line:
            continue
        if line.startswith("[") and line.endswith("]") and not line.startswith("[["):
            table = result
            for part in line[1:-1].strip().split("."):
                table = table.setdefault(part.strip().strip("\"'"), {})
            continue
        key, separator, value = line.partition("=")
        if not separator:
            raise ProjectError("%s:%d: expected key = value" % (where, number))
        key, value = key.strip().strip("\"'"), value.strip()
        if value.count("[") > value.count("]"):
            pending = (table, [value], key, number)
            continue
        table[key] = _value(value, "%s:%d" % (where, number))
    if pending is not None:
        raise ProjectError("%s: an array is not closed" % where)
    return result


def read_toml(path):
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise ProjectError("cannot read %s: %s" % (path, error)) from None
    try:
        import tomllib
    except ImportError:
        return _read_toml_subset(text, str(path))
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        raise ProjectError("%s: %s" % (path, error)) from None


# ---------------------------------------------------------------- finding and loading

def _table(path):
    """The AIL table of a config file, or None when the file has none."""
    data = read_toml(path)
    if path.name == "pyproject.toml":
        table = data.get("tool", {}).get("ail") if isinstance(data.get("tool"), dict) else None
    else:
        table = data
    return table if isinstance(table, dict) else None


def find(start):
    """The Project whose root is `start` or the nearest directory above it; None when there is none.
    Raises ProjectError when a config file is found but wrong."""
    start = Path(start).resolve()
    for directory in (start, *start.parents):
        for name in CONFIG_NAMES:
            candidate = directory / name
            if candidate.is_file():
                table = _table(candidate)
                if table is not None:
                    return load(candidate, table)
    return None


def load(config_file, table=None):
    config_file = Path(config_file).resolve()
    table = _table(config_file) if table is None else table
    if table is None:
        raise ProjectError("%s has no AIL configuration" % config_file)
    where = str(config_file) + (" [tool.ail]" if config_file.name == "pyproject.toml" else "")
    for key, value in table.items():
        if key not in KEYS:
            raise ProjectError("%s: unknown key %r (known: %s)" % (where, key, ", ".join(sorted(KEYS))))
        if not isinstance(value, KEYS[key]):
            raise ProjectError("%s: %s must be %s" % (where, key, {str: "a string", list: "a list", bool: "true or false"}[KEYS[key]]))
    root = config_file.parent
    if "entry" not in table:
        raise ProjectError("%s: entry is required (the entry module, for example entry = \"src/main.py\")" % where)
    name = table.get("name") or root.name
    if not NAME_PATTERN.match(name):
        raise ProjectError("%s: name %r must start with a letter or _ and use letters, digits, _ and -" % (where, name))
    entry = (root / table["entry"]).resolve()
    if entry.suffix.lower() not in (".py", ".ail") or not entry.is_file():
        raise ProjectError("%s: entry %r is not an existing .py or .ail file" % (where, table["entry"]))
    link = table.get("link", [])
    for library in link:
        if not isinstance(library, str) or not LIBRARY_PATTERN.match(library):
            raise ProjectError("%s: link entries are plain library names such as \"z\" (got %r)" % (where, library))
    module_path = []
    for directory in table.get("module_path", []):
        if not isinstance(directory, str):
            raise ProjectError("%s: module_path entries must be strings" % where)
        resolved = (root / directory).resolve()
        if not resolved.is_dir():
            raise ProjectError("%s: module_path %r is not a directory" % (where, directory))
        module_path.append(resolved)
    return Project(root, config_file, name, entry, list(link), bool(table.get("strict", False)), module_path)


# ---------------------------------------------------------------- ail new

def scaffold(destination):
    """Create the project directory `destination` (it must not exist) and return its path."""
    destination = Path(destination)
    name = destination.resolve().name
    if not NAME_PATTERN.match(name):
        raise ProjectError("project name %r must start with a letter or _ and use letters, digits, _ and -" % name)
    if destination.exists():
        raise ProjectError("%s already exists" % destination)
    (destination / "src").mkdir(parents=True)
    (destination / "ail.toml").write_text(CONFIG_TEMPLATE.format(name=name), encoding="utf-8")
    (destination / "src" / "main.py").write_text(MAIN_TEMPLATE.format(name=name), encoding="utf-8")
    (destination / ".gitignore").write_text(BUILD_DIRECTORY + "/\n", encoding="utf-8")
    return destination
