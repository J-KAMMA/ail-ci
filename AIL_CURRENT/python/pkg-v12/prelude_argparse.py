# -*- coding: utf-8 -*-
# prelude_argparse.py -- the `argparse` subset argparselib.py builds: long options and positionals, with
# int / float / str / pathlib.Path conversion, a default, choices and required=. Not built: short options,
# actions other than the default store, nargs, subcommands, groups, help text and the help action.


class _AilArgumentParser:
    def __init__(self, description: str, prog: str, add_help: bool) -> None:
        self.names: list[str] = []
        self.dests: list[str] = []
        self.kinds: list[str] = []
        self.convs: list[str] = []
        self.reqs: list[bool] = []
        self.defaults: list[str] = []
        self.choices: list[list[str]] = []
        self.description = description
        self.prog = prog
        self.add_help = add_help

    def add_argument(self, name: str, dest: str, kind: str, conv: str, required: bool,
                     default: str, choices: list[str]) -> None:
        self.names.append(name)
        self.dests.append(dest)
        self.kinds.append(kind)
        self.convs.append(conv)
        self.reqs.append(required)
        self.defaults.append(default)
        self.choices.append(choices)

    def _find(self, name: str) -> int:
        matches: list[int] = []
        i = 0
        while i < len(self.names):
            if self.kinds[i] == "opt":
                if self.names[i] == name:
                    return i
                if self.names[i].startswith(name):
                    matches.append(i)
            i = i + 1
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            return -2
        return -1

    def _prog(self) -> str:
        if self.prog != "\x00":
            return self.prog
        text = sys.argv[0]
        slash = text.rfind("/")
        if slash >= 0:
            return text[slash + 1:]
        return text

    def _usage(self) -> str:
        parts = ["usage:", self._prog()]
        if self.add_help:
            parts.append("[-h]")
        i = 0
        while i < len(self.dests):
            if self.kinds[i] == "opt":
                text = self.names[i]
                if len(self.choices[i]) > 0:
                    text = text + " {" + ",".join(self.choices[i]) + "}"
                else:
                    text = text + " " + self.dests[i].upper()
                if not self.reqs[i]:
                    text = "[" + text + "]"
                parts.append(text)
            else:
                text = self.names[i]
                if len(self.choices[i]) > 0:
                    text = "{" + ",".join(self.choices[i]) + "}"
                parts.append(text)
            i = i + 1
        return " ".join(parts)

    def _error(self, message: str) -> None:
        sys.stderr.write(self._usage() + "\n")
        sys.stderr.write(self._prog() + ": error: " + message + "\n")
        sys.exit(2)

    def _choice(self, i: int, value: str) -> None:
        if len(self.choices[i]) == 0:
            return
        j = 0
        while j < len(self.choices[i]):
            if self.choices[i][j] == value:
                return
            j = j + 1
        names = []
        j = 0
        while j < len(self.choices[i]):
            names.append("'" + self.choices[i][j] + "'")
            j = j + 1
        self._error("argument " + self.names[i] + ": invalid choice: '" + value + "' (choose from "
                    + ", ".join(names) + ")")

    def _check_value(self, i: int, value: str) -> None:
        if self.convs[i] == "int":
            try:
                int(value)
            except ValueError:
                self._error("argument " + self.names[i] + ": invalid int value: '" + value + "'")
        elif self.convs[i] == "float":
            try:
                float(value)
            except ValueError:
                self._error("argument " + self.names[i] + ": invalid float value: '" + value + "'")

    def parse_args(self, argv: list[str]) -> dict[str, str]:
        values: dict[str, str] = {}
        seen: dict[str, int] = {}
        extras: list[str] = []
        i = 0
        pos = 0
        ended = False
        separator = False
        while i < len(argv):
            token = argv[i]
            i = i + 1
            if not ended and token == "--":
                ended = True
                separator = True
                continue
            if not ended and token.startswith("--") and len(token) > 2:
                body = token[2:]
                equal = body.find("=")
                name = "--" + body
                value = ""
                has_value = False
                if equal >= 0:
                    name = "--" + body[:equal]
                    value = body[equal + 1:]
                    has_value = True
                found = self._find(name)
                if found == -2:
                    names = []
                    i = 0
                    while i < len(self.names):
                        if self.kinds[i] == "opt" and self.names[i].startswith(name):
                            names.append(self.names[i])
                        i = i + 1
                    self._error("ambiguous option: " + name + " could match " + ", ".join(names))
                if found < 0 or self.kinds[found] != "opt":
                    if separator:
                        extras.append("--")
                        separator = False
                    extras.append(token)
                    continue
                if not has_value:
                    if i >= len(argv) or (argv[i].startswith("-") and len(argv[i]) > 1
                                          and not _ail_argparse_negative(argv[i])):
                        self._error("argument " + name + ": expected one argument")
                    value = argv[i]
                    i = i + 1
                self._choice(found, value)
                self._check_value(found, value)
                values[self.dests[found]] = value
                seen[self.dests[found]] = 1
                continue
            if not ended and token.startswith("-") and len(token) > 1 \
                    and not _ail_argparse_negative(token):
                extras.append(token)
                continue
            while pos < len(self.dests) and self.kinds[pos] != "pos":
                pos = pos + 1
            if pos >= len(self.dests):
                if separator:
                    extras.append("--")
                    separator = False
                extras.append(token)
                continue
            self._choice(pos, token)
            self._check_value(pos, token)
            values[self.dests[pos]] = token
            seen[self.dests[pos]] = 1
            pos = pos + 1
            separator = False
        i = 0
        while i < len(self.dests):
            if self.dests[i] not in values and self.defaults[i] != "\x00":
                self._check_value(i, self.defaults[i])
            i = i + 1
        missing = []
        i = 0
        while i < len(self.dests):
            if self.kinds[i] == "opt" and self.reqs[i] and self.dests[i] not in seen:
                missing.append(self.names[i])
            if self.kinds[i] == "pos" and self.dests[i] not in seen:
                missing.append(self.names[i])
            i = i + 1
        if len(missing) > 0:
            self._error("the following arguments are required: " + ", ".join(missing))
        if len(extras) > 0:
            self._error("unrecognized arguments: " + " ".join(extras))
        i = 0
        while i < len(self.dests):
            if self.dests[i] not in values:
                values[self.dests[i]] = self.defaults[i]
            i = i + 1
        return values


def _ail_argparse_negative(text: str) -> bool:
    if len(text) < 2 or text[0] != "-":
        return False
    body = text[1:]
    dot = body.find(".")
    if dot < 0:
        return body.isdigit()
    before = body[:dot]
    after = body[dot + 1:]
    if len(after) == 0:
        return False
    i = 0
    while i < len(before):
        if not before[i].isdigit():
            return False
        i = i + 1
    i = 0
    while i < len(after):
        if not after[i].isdigit():
            return False
        i = i + 1
    return True


def _ail_argparse_get(values: dict[str, str], dest: str, conv: str):
    value = values.get(dest, "\x00")
    if value == "\x00":
        return None
    if conv == "int":
        return int(value)
    if conv == "float":
        return float(value)
    return value
