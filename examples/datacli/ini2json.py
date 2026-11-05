"""ini2json -- convert a small INI dialect to JSON on standard output.

A section is "[name]".  A setting is "key = value" or "key: value".  Lines
whose first non-blank character is ";" or "#" are comments.  Keys are
lowercased and values stripped; a key before any section goes to DEFAULT.
The result is printed as json.dumps(result, indent=2, sort_keys=True).  A line
that cannot be parsed prints "ini2json: line N: bad line" on stderr and exits 1.
"""

import json
import sys
from dataclasses import dataclass


@dataclass
class Section:
    name: str
    keys: list[str]
    values: list[str]


def find_cut(line: str) -> int:
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == "=" or ch == ":":
            return i
        i += 1
    return -1


def parse(text: str) -> tuple[list[Section], int]:
    sections: list[Section] = []
    current = Section("DEFAULT", [], [])
    sections.append(current)
    positions: dict[str, int] = {"DEFAULT": 0}
    lineno = 0
    for raw in text.splitlines():
        lineno += 1
        line = raw.strip()
        if line == "":
            continue
        first = line[0]
        if first == ";" or first == "#":
            continue
        if first == "[":
            if line[len(line) - 1] != "]":
                return sections, lineno
            name = line[1:len(line) - 1].strip()
            if name == "":
                return sections, lineno
            if name in positions:
                current = sections[positions[name]]
            else:
                positions[name] = len(sections)
                current = Section(name, [], [])
                sections.append(current)
            continue
        cut = find_cut(line)
        if cut <= 0:
            return sections, lineno
        key = line[:cut].strip().lower()
        if key == "":
            return sections, lineno
        value = line[cut + 1:].strip()
        current.keys.append(key)
        current.values.append(value)
    return sections, 0


def dump_section(section: Section) -> str:
    inner: dict[str, str] = {}
    i = 0
    while i < len(section.keys):
        inner[section.keys[i]] = section.values[i]
        i += 1
    body = json.dumps(inner, indent=2, sort_keys=True)
    lines: list[str] = body.split("\n")
    name: str = section.name
    out = "  " + json.dumps(name) + ": " + lines[0]
    j = 1
    while j < len(lines):
        out = out + "\n  " + lines[j]
        j += 1
    return out


def main() -> int:
    parsed = parse(sys.stdin.read())
    sections, bad = parsed
    if bad:
        sys.stderr.write("ini2json: line %d: bad line\n" % bad)
        return 1
    by_name: dict[str, int] = {}
    i = 0
    while i < len(sections):
        by_name[sections[i].name] = i
        i += 1
    names: list[str] = list(by_name.keys())
    names.sort()
    parts: list[str] = []
    for name in names:
        parts.append(dump_section(sections[by_name[name]]))
    text = "{\n" + ",\n".join(parts) + "\n}\n"
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
