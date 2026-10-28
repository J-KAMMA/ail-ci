# Helpers for the argparse lowering (arglib.py).  Ordinary Python: CPython can import this file
# and compare it with argparse.ArgumentParser for the supported subset.
import sys

_AIL_NOT_OPTION = -1
_AIL_UNKNOWN_OPTION = -2


def _ail_argparse_choice_str(choice) -> str:
    if isinstance(choice, str):
        return choice
    if choice is None:
        return str(choice)
    if isinstance(choice, int):
        return str(choice)
    if isinstance(choice, float):
        return str(choice)
    return choice.s


def _ail_argparse_choice_repr(choice) -> str:
    if isinstance(choice, str) or choice is None or isinstance(choice, int) or isinstance(choice, float):
        return repr(choice)
    return "PosixPath(" + repr(choice.s) + ")"


class _AilArgumentParser:
    def __init__(self, prog=None, description=None, add_help=True, allow_abbrev=True) -> None:
        self._attached = ""
        self._has_attached = False
        self.prog = prog
        self.description = description
        self.add_help = add_help
        self.allow_abbrev = allow_abbrev
        self.actions = []
        if add_help:
            self.actions.append({
                "names": ["-h", "--help"],
                "option": True,
                "dest": "help",
                "type": None,
                "default": None,
                "required": False,
                "choices": None,
                "help": "show this help message and exit",
                "metavar": None,
                "action": "help",
            })

    def add_argument(self, *names, action="store", nargs=None, const=None, default=None, type=None,
                     choices=None, required=False, help=None, metavar=None, dest=None,
                     _ail_type_name=None) -> None:
        option = False
        for name in names:
            if name.startswith("-"):
                option = True
        if dest is None:
            if option:
                dest = None
                for name in names:
                    if name.startswith("--"):
                        dest = name
                        break
                if dest is None:
                    dest = names[0]
                while dest.startswith("-"):
                    dest = dest[1:]
                dest = dest.replace("-", "_")
            else:
                dest = names[0]
        if option:
            if not required:
                required = False
        else:
            required = True
        self.actions.append({
            "names": list(names),
            "option": option,
            "dest": dest,
            "type": type,
            "type_name": _ail_type_name,
            "default": default,
            "required": required,
            "choices": choices,
            "help": help,
            "metavar": metavar,
            "action": action,
        })

    def _prog(self) -> str:
        if self.prog is not None:
            return self.prog
        name = sys.argv[0]
        cut = name.rfind("/")
        other = name.rfind("\\")
        if other > cut:
            cut = other
        if cut >= 0:
            return name[cut + 1:]
        return name

    def _display_name(self, action) -> str:
        if action["option"]:
            return "/".join(action["names"])
        return action["dest"]

    def _metavar(self, action) -> str:
        if action["metavar"] is not None:
            return action["metavar"]
        if action["choices"] is not None:
            return self._choices_text(action["choices"])
        if action["option"]:
            return action["dest"].upper()
        return action["dest"]

    def _choices_text(self, choices) -> str:
        parts = []
        for value in choices:
            parts.append(_ail_argparse_choice_str(value))
        return "{" + ",".join(parts) + "}"

    def _choices_list(self, choices) -> str:
        parts = []
        for value in choices:
            parts.append(_ail_argparse_choice_repr(value))
        return ", ".join(parts)

    def _usage_part(self, action) -> str:
        if action["action"] == "help":
            return "[" + action["names"][0] + "]"
        if not action["option"]:
            return self._metavar(action)
        part = action["names"][0] + " " + self._metavar(action)
        if not action["required"]:
            part = "[" + part + "]"
        return part

    def _get_lines(self, parts, indent, prefix):
        lines = []
        line = []
        indent_length = len(indent)
        if prefix is not None:
            line_length = len(prefix) - 1
        else:
            line_length = indent_length - 1
        for part in parts:
            if line_length + 1 + len(part) > 78 and line:
                lines.append(indent + " ".join(line))
                line = []
                line_length = indent_length - 1
            line.append(part)
            line_length = line_length + len(part) + 1
        if line:
            lines.append(indent + " ".join(line))
        if prefix is not None:
            lines[0] = lines[0][indent_length:]
        return lines

    def _usage(self) -> str:
        optionals = []
        positionals = []
        for action in self.actions:
            if action["option"]:
                optionals.append(action)
            else:
                positionals.append(action)
        opt_parts = []
        for action in optionals:
            opt_parts.append(self._usage_part(action))
        pos_parts = []
        for action in positionals:
            pos_parts.append(self._usage_part(action))
        prog = self._prog()
        prefix = "usage: "
        body = " ".join(opt_parts + pos_parts)
        usage = prog
        if body != "":
            usage = prog + " " + body
        if len(prefix) + len(usage) <= 78:
            return prefix + usage
        if len(prefix) + len(prog) <= 58:
            indent = " " * (len(prefix) + len(prog) + 1)
            if opt_parts:
                lines = self._get_lines([prog] + opt_parts, indent, prefix)
                if pos_parts:
                    lines.extend(self._get_lines(pos_parts, indent, None))
            elif pos_parts:
                lines = self._get_lines([prog] + pos_parts, indent, prefix)
            else:
                lines = [prog]
        else:
            indent = " " * len(prefix)
            parts = opt_parts + pos_parts
            lines = self._get_lines(parts, indent, None)
            if len(lines) > 1:
                lines = []
                lines.extend(self._get_lines(opt_parts, indent, None))
                lines.extend(self._get_lines(pos_parts, indent, None))
            lines = [prog] + lines
        return prefix + "\n".join(lines)

    def _invocation(self, action) -> str:
        if not action["option"]:
            return self._metavar(action)
        if action["action"] == "help":
            return ", ".join(action["names"])
        metavar = self._metavar(action)
        parts = []
        for name in action["names"]:
            parts.append(name + " " + metavar)
        return ", ".join(parts)

    def _wrap(self, text, width):
        words = text.split()
        lines = []
        line = ""
        for word in words:
            if line == "":
                line = word
            elif len(line) + 1 + len(word) <= width:
                line = line + " " + word
            else:
                lines.append(line)
                line = word
        if line != "":
            lines.append(line)
        return lines

    def _format_action(self, action, help_position) -> str:
        invocation = self._invocation(action)
        help_width = 78 - help_position
        if help_width < 11:
            help_width = 11
        action_width = help_position - 4
        if action["help"] is None or action["help"].strip() == "":
            return "  " + invocation + "\n"
        lines = self._wrap(action["help"], help_width)
        if len(invocation) <= action_width:
            text = "  " + invocation
            while len(text) < help_position:
                text = text + " "
            text = text + lines[0] + "\n"
        else:
            text = "  " + invocation + "\n"
            spaces = ""
            while len(spaces) < help_position:
                spaces = spaces + " "
            text = text + spaces + lines[0] + "\n"
        for k in range(1, len(lines)):
            spaces = ""
            while len(spaces) < help_position:
                spaces = spaces + " "
            text = text + spaces + lines[k] + "\n"
        return text

    def format_help(self) -> str:
        text = self._usage() + "\n\n"
        if self.description is not None:
            for line in self._wrap(self.description, 78):
                text = text + line + "\n"
            text = text + "\n"
        positionals = []
        optionals = []
        for action in self.actions:
            if action["option"]:
                optionals.append(action)
            else:
                positionals.append(action)
        maximum = 0
        for action in self.actions:
            length = len(self._invocation(action)) + 2
            if length > maximum:
                maximum = length
        help_position = maximum + 2
        if help_position > 24:
            help_position = 24
        if positionals:
            text = text + "positional arguments:\n"
            for action in positionals:
                text = text + self._format_action(action, help_position)
            text = text + "\n"
        if optionals:
            text = text + "options:\n"
            for action in optionals:
                text = text + self._format_action(action, help_position)
            text = text + "\n"
        return text.rstrip("\n") + "\n"

    def _is_negative(self, token) -> bool:
        if len(token) < 2 or token[0] != "-":
            return False
        rest = token[1:]
        return _ail_argparse_negative(rest)

    def _looks_option(self, token) -> bool:
        if len(token) < 2 or token[0] != "-":
            return False
        if token == "--":
            return True
        if self._match(token) >= 0:
            return True
        if self._is_negative(token):
            return self._has_negative_options()
        return True

    def _match(self, token) -> int:
        self._attached = ""
        self._has_attached = False
        body = token
        if token.startswith("--"):
            if "=" in token:
                cut = token.find("=")
                body = token[:cut]
                self._attached = token[cut + 1:]
                self._has_attached = True
            for position in range(len(self.actions)):
                action = self.actions[position]
                for name in action["names"]:
                    if name == body:
                        return position
            if self.allow_abbrev:
                found = []
                for position in range(len(self.actions)):
                    action = self.actions[position]
                    hit = False
                    for name in action["names"]:
                        if name.startswith("--") and name.startswith(body):
                            hit = True
                    if hit:
                        found.append(position)
                if len(found) == 1:
                    return found[0]
                if len(found) > 1:
                    names = []
                    for position in found:
                        action = self.actions[position]
                        for name in action["names"]:
                            if name.startswith("--") and name.startswith(body):
                                names.append(name)
                    self._error("ambiguous option: " + body + " could match " + ", ".join(names))
            return -1
        for position in range(len(self.actions)):
            action = self.actions[position]
            for name in action["names"]:
                if name == token:
                    return position
        if len(token) > 2:
            head = token[:2]
            rest = token[2:]
            if rest.startswith("="):
                rest = rest[1:]
            for position in range(len(self.actions)):
                action = self.actions[position]
                for name in action["names"]:
                    if name == head and not name.startswith("--"):
                        self._attached = rest
                        self._has_attached = True
                        return position
        return -1

    def _type_label(self, action) -> str:
        if action["type_name"] is not None:
            return action["type_name"]
        return "value"

    def _builtin_value(self, label, text):
        if label == "int":
            return int(text)
        if label == "float":
            return float(text)
        if label == "bool":
            return bool(text)
        return text

    def _convert(self, action, text):
        if action["action"] == "help":
            return text
        if action["type"] is None and action["type_name"] is None:
            value = text
        elif action["type"] is None and action["type_name"] == "Path":
            value = text
        elif action["type"] is None:
            try:
                value = self._builtin_value(action["type_name"], text)
            except ValueError:
                self._error("argument " + self._display_name(action) + ": invalid " +
                            self._type_label(action) + " value: " + repr(text))
                return None
            except TypeError:
                self._error("argument " + self._display_name(action) + ": invalid " +
                            self._type_label(action) + " value: " + repr(text))
                return None
        else:
            try:
                value = action["type"](text)
            except ValueError:
                self._error("argument " + self._display_name(action) + ": invalid " +
                            self._type_label(action) + " value: " + repr(text))
                return None
            except TypeError:
                self._error("argument " + self._display_name(action) + ": invalid " +
                            self._type_label(action) + " value: " + repr(text))
                return None
        if action["choices"] is not None:
            found = False
            if action["type_name"] == "Path":
                for choice in action["choices"]:
                    if isinstance(choice, str) or choice is None or isinstance(choice, int) or isinstance(choice, float):
                        continue
                    if choice.s == value:
                        found = True
            else:
                found = value in action["choices"]
            if not found:
                if action["type_name"] == "Path":
                    shown = "PosixPath(" + repr(value) + ")"
                else:
                    shown = repr(value)
                self._error("argument " + self._display_name(action) + ": invalid choice: " +
                            shown + " (choose from " + self._choices_list(action["choices"]) + ")")
        return value

    def _error(self, message) -> None:
        print(self._usage(), file=sys.stderr)
        print(self._prog() + ": error: " + message, file=sys.stderr)
        sys.exit(2)

    def _has_negative_options(self) -> bool:
        for action in self.actions:
            for name in action["names"]:
                if self._is_negative(name):
                    return True
        return False

    def _option_like(self, token) -> int:
        if token == "" or token[0] != "-" or token == "-":
            return _AIL_NOT_OPTION
        if token == "--":
            return _AIL_NOT_OPTION
        position = self._match(token)
        if position >= 0:
            return position
        if self._is_negative(token) and not self._has_negative_options():
            return _AIL_NOT_OPTION
        if " " in token:
            return _AIL_NOT_OPTION
        return _AIL_UNKNOWN_OPTION

    def _consume_positionals(self, tokens, pattern, start, remaining) -> int:
        for count in range(len(remaining), 0, -1):
            position = start
            ok = True
            for step in range(count):
                while position < len(pattern) and pattern[position] == "-":
                    position = position + 1
                if position >= len(pattern) or pattern[position] != "A":
                    ok = False
                    break
                position = position + 1
                while position < len(pattern) and pattern[position] == "-":
                    position = position + 1
            if ok:
                del remaining[:count]
                return position
        return start

    def _extras(self, tokens):
        pattern = []
        options = {}
        index = 0
        while index < len(tokens):
            token = tokens[index]
            if token == "--":
                pattern.append("-")
                index = index + 1
                while index < len(tokens):
                    pattern.append("A")
                    index = index + 1
                break
            found = self._option_like(token)
            if found == _AIL_NOT_OPTION:
                pattern.append("A")
            else:
                pattern.append("O")
                options[index] = found
            index = index + 1
        remaining = []
        for position in range(len(self.actions)):
            if not self.actions[position]["option"]:
                remaining.append(position)
        extras = []
        start = 0
        maximum = -1
        for position in options:
            if position > maximum:
                maximum = position
        while start <= maximum:
            next_option = -1
            for position in options:
                if position >= start and (next_option == -1 or position < next_option):
                    next_option = position
            if start != next_option:
                end = self._consume_positionals(tokens, pattern, start, remaining)
                start = end
                if end > next_option:
                    continue
                if end > start:
                    continue
            if start not in options:
                extras.extend(tokens[start:next_option])
                start = next_option
            code = options[start]
            if code == _AIL_UNKNOWN_OPTION:
                extras.append(tokens[start])
                start = start + 1
            else:
                self._match(tokens[start])
                if self._has_attached:
                    start = start + 1
                elif start + 1 < len(tokens) and pattern[start + 1] == "A":
                    start = start + 2
                else:
                    start = start + 1
        stop = self._consume_positionals(tokens, pattern, start, remaining)
        extras.extend(tokens[stop:])
        return extras

    def parse_args(self, args=None):
        if args is None:
            tokens = sys.argv[1:]
        else:
            tokens = list(args)
        result = {}
        given = []
        for action in self.actions:
            given.append(False)
            if action["option"]:
                value = action["default"]
                if isinstance(value, str) and action["type_name"] is not None:
                    value = self._convert(action, value)
                result[action["dest"]] = value
        positionals = []
        for action in self.actions:
            if not action["option"]:
                positionals.append(action)
        used = []
        for action in positionals:
            used.append(False)
        after = False
        index = 0
        while index < len(tokens):
            token = tokens[index]
            if not after and token == "--":
                after = True
                index = index + 1
                continue
            if not after and self._looks_option(token):
                position = self._match(token)
                if position < 0:
                    index = index + 1
                    continue
                action = self.actions[position]
                if action["action"] == "help":
                    if self._has_attached:
                        self._error("argument " + self._display_name(action) +
                                    ": ignored explicit argument " + repr(self._attached))
                    print(self.format_help(), end="")
                    sys.exit(0)
                given[position] = True
                if self._has_attached:
                    text = self._attached
                    index = index + 1
                else:
                    if index + 1 >= len(tokens):
                        self._error("argument " + self._display_name(action) + ": expected one argument")
                        return None
                    following = tokens[index + 1]
                    if self._looks_option(following):
                        self._error("argument " + self._display_name(action) + ": expected one argument")
                        return None
                    text = following
                    index = index + 2
                result[action["dest"]] = self._convert(action, text)
                continue
            placed = False
            for position in range(len(positionals)):
                if not used[position]:
                    used[position] = True
                    result[positionals[position]["dest"]] = self._convert(positionals[position], token)
                    placed = True
                    break
            if not placed:
                pass
            index = index + 1
        missing = []
        for position in range(len(self.actions)):
            action = self.actions[position]
            if action["action"] == "help":
                continue
            if action["option"]:
                if action["required"] and not given[position]:
                    missing.append(self._display_name(action))
            else:
                found = False
                for entry in range(len(positionals)):
                    if positionals[entry] is action and used[entry]:
                        found = True
                if not found:
                    missing.append(self._display_name(action))
        if missing:
            self._error("the following arguments are required: " + ", ".join(missing))
        extras = self._extras(tokens)
        if extras:
            self._error("unrecognized arguments: " + " ".join(extras))
        return _AilNamespace(result)


def _ail_argparse_negative(rest) -> bool:
    if rest == "":
        return False
    dots = 0
    digits = 0
    for index in range(len(rest)):
        char = rest[index]
        if char >= "0" and char <= "9":
            digits = digits + 1
        elif char == ".":
            dots = dots + 1
        else:
            return False
    if digits == 0:
        return False
    return dots <= 1
