"""The stdlib `argparse` module for AIL: ArgumentParser, add_argument, parse_args and the
common actions, nargs forms, choices, types, defaults and help output, written in AIL's Python
subset. Programs that use a name this file does not define are refused at build time by the
module checker; subparsers, FileType, parse_intermixed_args and catching SystemExit are follow-ups.
"""
import sys

SUPPRESS = "==SUPPRESS=="
OPTIONAL = "?"
ZERO_OR_MORE = "*"
ONE_OR_MORE = "+"
PARSER = "A"
REMAINDER = "..."


def _quote(text):
    if not isinstance(text, str):
        return repr(text)
    single = "'" in text and '"' not in text
    quote = '"' if single else "'"
    out = []
    for ch in text:
        if ch == quote or ch == "\\":
            out.append("\\")
        out.append(ch)
    return quote + "".join(out) + quote


def _type_name(value):
    return "value"


def _looks_negative(token):
    if len(token) < 2 or token[0] != "-":
        return False
    body = token[1:]
    digits = 0
    dots = 0
    for i in range(len(body)):
        ch = body[i]
        if ch >= "0" and ch <= "9":
            digits = digits + 1
        elif ch == ".":
            dots = dots + 1
        else:
            return False
    return digits > 0 and dots <= 1


def _wrap(text, width, indent):
    words = text.split()
    if not words:
        return [""]
    lines = []
    line = words[0]
    for word in words[1:]:
        if len(line) + 1 + len(word) <= width:
            line = line + " " + word
        else:
            lines.append(line)
            line = word
    lines.append(line)
    return lines


def _copy_items(items):
    if items is None:
        return []
    if isinstance(items, list):
        copied = []
        for item in items:
            copied.append(item)
        return copied
    return items


def _metavar(action):
    if action["metavar"] is not None:
        return action["metavar"]
    if action["choices"] is not None:
        names = []
        for choice in action["choices"]:
            names.append(str(choice))
        return "{" + ",".join(names) + "}"
    if action["positional"]:
        return action["dest"]
    return action["dest"].upper()


def _metavar_item(action, index):
    metavar = action["metavar"]
    if isinstance(metavar, (tuple, list)):
        if index < len(metavar):
            return metavar[index]
    return _metavar(action)


def _names(action):
    if action["positional"]:
        return _metavar(action)
    names = []
    for option in action["option_strings"]:
        name = option
        if action["action"] not in ("store_true", "store_false", "store_const", "append_const", "count", "help", "version"):
            nargs = action["nargs"]
            if nargs is None:
                name = name + " " + _metavar(action)
            elif nargs == OPTIONAL:
                name = name + " [" + _metavar(action) + "]"
            elif nargs == ZERO_OR_MORE:
                name = name + " [" + _metavar(action) + " ...]"
            elif nargs == ONE_OR_MORE:
                name = name + " " + _metavar(action) + " [" + _metavar(action) + " ...]"
            elif isinstance(nargs, int):
                parts = []
                for index in range(nargs):
                    parts.append(_metavar_item(action, index))
                name = name + " " + " ".join(parts)
        names.append(name)
    return ", ".join(names)


def _group_piece(group):
    inner = []
    for member in group._actions:
        if member["help"] != SUPPRESS:
            inner.append(_usage_piece(member).strip("[]"))
    if group._required:
        if len(inner) > 1:
            return "(" + " | ".join(inner) + ")"
        if len(inner) == 1:
            return inner[0]
        return ""
    return "[" + " | ".join(inner) + "]"


def _usage_piece(action):
    if action["positional"]:
        nargs = action["nargs"]
        metavar = _metavar(action)
        if nargs is None:
            return metavar
        if nargs == OPTIONAL:
            return "[" + metavar + "]"
        if nargs == ZERO_OR_MORE:
            return "[" + metavar + " ...]"
        if nargs == ONE_OR_MORE:
            return metavar + " [" + metavar + " ...]"
        if isinstance(nargs, int):
            parts = []
            for index in range(nargs):
                parts.append(_metavar_item(action, index))
            return " ".join(parts)
        return metavar
    name = action["option_strings"][0]
    action_name = action["action"]
    if action_name in ("store_true", "store_false", "store_const", "append_const", "count", "help", "version"):
        piece = name
        if action["required"]:
            return piece
        return "[" + piece + "]"
    nargs = action["nargs"]
    metavar = _metavar(action)
    if nargs is None:
        piece = name + " " + metavar
    elif nargs == OPTIONAL:
        piece = name + " [" + metavar + "]"
    elif nargs == ZERO_OR_MORE:
        piece = name + " [" + metavar + " ...]"
    elif nargs == ONE_OR_MORE:
        piece = name + " " + metavar + " [" + metavar + " ...]"
    elif isinstance(nargs, int):
        parts = []
        for index in range(nargs):
            parts.append(_metavar_item(action, index))
        piece = name + " " + " ".join(parts)
    else:
        piece = name
    if action["required"]:
        return piece
    return "[" + piece + "]"


class Namespace:
    def __init__(self):
        self._ail_values = {}
        self._ail_order = []

    def _ail_set(self, name, value):
        if name not in self._ail_values:
            self._ail_order.append(name)
        self._ail_values[name] = value
        if value is None:
            setattr(self, name, None)
        else:
            setattr(self, name, value)

    def __repr__(self):
        parts = []
        for name in self._ail_order:
            parts.append(name + "=" + repr(self._ail_values[name]))
        return "Namespace(" + ", ".join(parts) + ")"


class _ArgumentGroup:
    def __init__(self, parser, exclusive=False):
        self._parser = parser
        self._actions = []
        self._exclusive = exclusive

    def add_argument(self, *args, **kwargs):
        action = self._parser._ail_add(args, kwargs)
        if self._exclusive:
            action["group"] = self
        self._actions.append(action)
        return action


class _MutuallyExclusiveGroup(_ArgumentGroup):
    def __init__(self, parser, required):
        _ArgumentGroup.__init__(self, parser, True)
        self._required = required


class HelpFormatter:
    pass


class RawDescriptionHelpFormatter(HelpFormatter):
    pass


class RawTextHelpFormatter(RawDescriptionHelpFormatter):
    pass


class ArgumentDefaultsHelpFormatter(HelpFormatter):
    pass


class MetavarTypeHelpFormatter(HelpFormatter):
    pass


class _HelpAction:
    pass


class _VersionAction:
    pass


class ArgumentParser:
    def __init__(self, prog=None, usage=None, description=None, epilog=None, add_help=True,
                 prefix_chars="-", allow_abbrev=True, formatter_class=None, argument_default=None,
                 conflict_handler="error"):
        if prog is None:
            prog = sys.argv[0]
            if "/" in prog:
                prog = prog.rsplit("/", 1)[1]
        self.prog = prog
        self.usage = usage
        self.description = description
        self.epilog = epilog
        self.prefix_chars = prefix_chars
        self.allow_abbrev = allow_abbrev
        self.formatter_class = formatter_class
        self.argument_default = argument_default
        self.conflict_handler = conflict_handler
        self._ail_actions = []
        self._ail_groups = []
        if add_help:
            action = self._ail_add(("-h", "--help"), {"action": "help",
                                                      "help": "show this help message and exit"})
            action["default"] = SUPPRESS

    def _ail_find(self, option):
        for action in self._ail_actions:
            for name in action["option_strings"]:
                if name == option:
                    return action
        if self.allow_abbrev and option.startswith("--") and "=" not in option:
            found = []
            for action in self._ail_actions:
                for name in action["option_strings"]:
                    if name.startswith(option) and name != option:
                        if action not in found:
                            found.append(action)
            if len(found) == 1:
                return found[0]
        return None

    def _ail_add(self, args, kwargs):
        option_strings = []
        positional = True
        for name in args:
            option_strings.append(name)
            if name and name[0] in self.prefix_chars:
                positional = False
        if not option_strings:
            raise ValueError("add_argument needs a name")
        action_name = kwargs.get("action", None)
        if action_name is None:
            action_name = "store"
        if action_name == "help":
            action_name = "help"
        elif action_name == "version":
            action_name = "version"
        if positional:
            if len(option_strings) != 1:
                raise ValueError("a positional argument takes one name")
            dest = kwargs.get("dest", option_strings[0])
        else:
            dest = kwargs.get("dest", None)
            if dest is None:
                for name in option_strings:
                    if name.startswith("--"):
                        dest = name[2:]
                        break
                if dest is None:
                    dest = option_strings[0].lstrip(self.prefix_chars)
            dest = dest.replace("-", "_")
        default = kwargs.get("default", None)
        if "default" not in kwargs:
            if action_name == "store_true":
                default = False
            elif action_name == "store_false":
                default = True
            elif action_name == "help" or action_name == "version":
                default = SUPPRESS
            elif action_name == "count":
                default = None
            else:
                default = self.argument_default
        nargs = kwargs.get("nargs", None)
        if action_name in ("store_true", "store_false", "store_const", "append_const", "count", "help", "version"):
            nargs = 0
        action = {
            "option_strings": option_strings,
            "dest": dest,
            "action": action_name,
            "nargs": nargs,
            "const": kwargs.get("const", None),
            "default": default,
            "type": kwargs.get("type", None),
            "choices": kwargs.get("choices", None),
            "required": kwargs.get("required", False),
            "help": kwargs.get("help", None),
            "metavar": kwargs.get("metavar", None),
            "version": kwargs.get("version", None),
            "positional": positional,
            "group": None,
        }
        if action_name == "help" and action["help"] is None:
            action["help"] = "show this help message and exit"
        if action_name == "version" and action["help"] is None:
            action["help"] = "show program's version number and exit"
        self._ail_actions.append(action)
        return action

    def add_argument(self, *args, **kwargs):
        return self._ail_add(args, kwargs)

    def add_argument_group(self, *args, **kwargs):
        return _ArgumentGroup(self)

    def add_mutually_exclusive_group(self, required=False):
        group = _MutuallyExclusiveGroup(self, required)
        self._ail_groups.append(group)
        return group

    def _ail_usage(self):
        if self.usage is not None:
            return "usage: " + self.usage
        ordered = []
        for action in self._ail_actions:
            if not action["positional"]:
                ordered.append(action)
        for action in self._ail_actions:
            if action["positional"]:
                ordered.append(action)
        pieces = []
        grouped = []
        for action in ordered:
            if action["help"] == SUPPRESS:
                continue
            group = action["group"]
            if group is not None:
                if group not in grouped:
                    grouped.append(group)
                    pieces.append(_group_piece(group))
                continue
            pieces.append(_usage_piece(action))
        prefix = "usage: " + self.prog
        if not pieces:
            return prefix
        full = prefix + " " + " ".join(pieces)
        if len(full) <= 80:
            return full
        opt_pieces = []
        pos_pieces = []
        for action in ordered:
            if action["help"] == SUPPRESS:
                continue
            group = action["group"]
            piece = _usage_piece(action)
            if group is not None:
                continue
            if action["positional"]:
                pos_pieces.append(piece)
            else:
                opt_pieces.append(piece)
        for group in grouped:
            opt_pieces.append(_group_piece(group))
        indent = " " * (len(prefix) + 1)
        lines = []
        line = prefix
        for piece in opt_pieces:
            if line == prefix:
                line = prefix + " " + piece
            elif len(line) + 1 + len(piece) <= 80:
                line = line + " " + piece
            else:
                lines.append(line)
                line = indent + piece
        lines.append(line)
        line = ""
        for piece in pos_pieces:
            if not line:
                line = indent + piece
            elif len(line) + 1 + len(piece) <= 80:
                line = line + " " + piece
            else:
                lines.append(line)
                line = indent + piece
        if line:
            lines.append(line)
        return "\n".join(lines)

    def _ail_help_lines(self, action, position):
        left = "  " + _names(action)
        text = action["help"]
        if not text:
            return [left]
        lines = []
        invocation = len(left) - 2
        action_width = position - 4
        if invocation <= action_width:
            prefix = left + " " * (position - len(left))
        else:
            lines.append(left)
            prefix = " " * position
        width = 78 - position
        if width < 11:
            width = 11
        wrapped = _wrap(text, width, position)
        lines.append(prefix + wrapped[0])
        for i in range(1, len(wrapped)):
            lines.append(" " * position + wrapped[i])
        return lines

    def format_help(self):
        out = [self._ail_usage()]
        if self.description:
            out.append("")
            out.extend(_wrap(self.description, 79, 0))
        positionals = []
        optionals = []
        for action in self._ail_actions:
            if action["help"] == SUPPRESS:
                continue
            if action["positional"]:
                positionals.append(action)
            else:
                optionals.append(action)
        longest = 0
        for action in self._ail_actions:
            if action["help"] == SUPPRESS:
                continue
            length = 2 + len(_names(action))
            if length > longest:
                longest = length
        position = longest + 2
        if position > 24:
            position = 24
        if position < 2:
            position = 2
        if positionals:
            out.append("")
            out.append("positional arguments:")
            for action in positionals:
                out.extend(self._ail_help_lines(action, position))
        if optionals:
            out.append("")
            out.append("options:")
            for action in optionals:
                out.extend(self._ail_help_lines(action, position))
        if self.epilog:
            out.append("")
            out.extend(_wrap(self.epilog, 79, 0))
        return "\n".join(out) + "\n"

    def print_help(self):
        print(self.format_help(), end="")

    def print_usage(self):
        print(self._ail_usage())

    def format_usage(self):
        return self._ail_usage() + "\n"

    def error(self, message):
        print(self._ail_usage(), file=sys.stderr)
        print(self.prog + ": error: " + message, file=sys.stderr)
        sys.exit(2)

    def exit(self, status=0, message=None):
        if message:
            print(message, end="", file=sys.stderr)
        sys.exit(status)

    def _ail_coerce(self, action, text):
        kind = action["type"]
        if kind is None:
            return text
        try:
            return kind(text)
        except ValueError as error:
            name = _type_name(kind)
            detail = str(error)
            if "int" in detail:
                name = "int"
            elif "float" in detail:
                name = "float"
            self.error("argument " + self._ail_arg_name(action) + ": invalid " + name +
                       " value: " + _quote(text))
        except TypeError as error:
            name = _type_name(kind)
            detail = str(error)
            if "int" in detail:
                name = "int"
            elif "float" in detail:
                name = "float"
            self.error("argument " + self._ail_arg_name(action) + ": invalid " + name +
                       " value: " + _quote(text))
        return text

    def _ail_check_value(self, action, value):
        choices = action["choices"]
        if choices is None:
            return
        if value not in choices:
            names = []
            for choice in choices:
                names.append(_quote(choice))
            self.error("argument " + self._ail_arg_name(action) + ": invalid choice: " + _quote(value) +
                       " (choose from " + ", ".join(names) + ")")

    def _ail_convert(self, action, text):
        value = self._ail_coerce(action, text)
        self._ail_check_value(action, value)
        return value

    def _ail_arg_name(self, action):
        if action["positional"]:
            return action["dest"]
        return "/".join(action["option_strings"])

    def _ail_store(self, namespace, action, raw):
        nargs = action["nargs"]
        if nargs is None:
            value = self._ail_convert(action, raw[0])
        elif nargs == OPTIONAL:
            if raw:
                value = self._ail_convert(action, raw[0])
            else:
                if action["positional"]:
                    value = action["default"]
                else:
                    value = action["const"]
                if isinstance(value, str):
                    value = self._ail_convert(action, value)
        elif nargs == ZERO_OR_MORE and action["positional"] and not raw:
            if action["default"] is not None:
                value = action["default"]
                self._ail_check_value(action, value)
            else:
                value = []
        else:
            values = []
            for item in raw:
                values.append(self._ail_convert(action, item))
            value = values
        name = action["dest"]
        action_name = action["action"]
        if action_name == "append":
            current = _copy_items(getattr(namespace, name, None))
            current.append(value)
            namespace._ail_set(name, current)
        else:
            namespace._ail_set(name, value)

    def _ail_apply(self, namespace, action, raw, seen):
        name = action["dest"]
        action_name = action["action"]
        if action_name == "help":
            self.print_help()
            self.exit(0)
        if action_name == "version":
            text = action["version"]
            if text is None:
                text = ""
            print(text)
            self.exit(0)
        seen.append(action)
        if action_name == "store_true":
            namespace._ail_set(name, True)
        elif action_name == "store_false":
            namespace._ail_set(name, False)
        elif action_name == "store_const":
            namespace._ail_set(name, action["const"])
        elif action_name == "append_const":
            current = _copy_items(getattr(namespace, name, None))
            current.append(action["const"])
            namespace._ail_set(name, current)
        elif action_name == "count":
            current = getattr(namespace, name, None)
            if current is None:
                current = 0
            namespace._ail_set(name, current + 1)
        else:
            self._ail_store(namespace, action, raw)

    def _ail_take_option_value(self, tokens, index, action, option):
        nargs = action["nargs"]
        if nargs == 0:
            return [], index
        if nargs is None:
            if index >= len(tokens) or tokens[index] == "--" or self._ail_is_option(tokens[index]):
                self.error("argument " + self._ail_arg_name(action) + ": expected one argument")
            return [tokens[index]], index + 1
        if nargs == OPTIONAL:
            if index < len(tokens) and not self._ail_is_option(tokens[index]):
                return [tokens[index]], index + 1
            return [], index
        if nargs == ZERO_OR_MORE or nargs == ONE_OR_MORE:
            out = []
            while index < len(tokens) and not self._ail_is_option(tokens[index]):
                out.append(tokens[index])
                index = index + 1
            if nargs == ONE_OR_MORE and not out:
                self.error("argument " + self._ail_arg_name(action) + ": expected at least one argument")
            return out, index
        if isinstance(nargs, int):
            out = []
            while len(out) < nargs and index < len(tokens) and not self._ail_is_option(tokens[index]):
                out.append(tokens[index])
                index = index + 1
            if len(out) < nargs:
                self.error("argument " + self._ail_arg_name(action) + ": expected " + str(nargs) + " arguments")
            return out, index
        return [], index

    def _ail_is_option(self, token):
        if not token or token[0] not in self.prefix_chars:
            return False
        if token == "-" or token == "--":
            return False
        if _looks_negative(token):
            return self._ail_find(token) is not None
        return True

    def parse_known_args(self, args=None, namespace=None):
        if args is None:
            tokens = list(sys.argv[1:])
        else:
            tokens = list(args)
        if namespace is None:
            namespace = Namespace()
        for action in self._ail_actions:
            if action["default"] is not SUPPRESS and not hasattr(namespace, action["dest"]):
                namespace._ail_set(action["dest"], action["default"])
        positional_tokens = []
        positional_positions = []
        extras = []
        extra_positions = []
        seen = []
        index = 0
        after_dashdash = False
        while index < len(tokens):
            token = tokens[index]
            index = index + 1
            if after_dashdash:
                positional_tokens.append(token)
                positional_positions.append(index - 1)
                continue
            if token == "--":
                after_dashdash = True
                continue
            if not self._ail_is_option(token):
                positional_tokens.append(token)
                positional_positions.append(index - 1)
                continue
            if token.startswith("--"):
                name = token
                explicit = None
                if "=" in token:
                    name, explicit = token.split("=", 1)
                action = self._ail_find(name)
                if action is None:
                    extras.append(token)
                    extra_positions.append(index - 1)
                    continue
                if action["nargs"] == 0:
                    if explicit is not None:
                        self.error("argument " + self._ail_arg_name(action) + ": ignored explicit argument " +
                                   _quote(explicit))
                    self._ail_apply(namespace, action, [], seen)
                else:
                    if explicit is not None:
                        raw = [explicit]
                    else:
                        raw, index = self._ail_take_option_value(tokens, index, action, name)
                    self._ail_apply(namespace, action, raw, seen)
                continue
            name = token
            rest = token[1:]
            pos = 0
            while pos < len(rest):
                short = "-" + rest[pos]
                action = self._ail_find(short)
                if action is None:
                    extras.append(token)
                    extra_positions.append(index - 1)
                    break
                if action["nargs"] == 0:
                    self._ail_apply(namespace, action, [], seen)
                    pos = pos + 1
                    continue
                tail = rest[pos + 1:]
                if tail:
                    self._ail_apply(namespace, action, [tail], seen)
                    pos = len(rest)
                else:
                    raw, index = self._ail_take_option_value(tokens, index, action, short)
                    self._ail_apply(namespace, action, raw, seen)
                    pos = len(rest)
        pos_index = 0
        for action in self._ail_actions:
            if not action["positional"]:
                continue
            nargs = action["nargs"]
            if nargs is None:
                need = 1
            elif isinstance(nargs, int):
                need = nargs
            elif nargs == OPTIONAL:
                need = 0
            elif nargs == ONE_OR_MORE:
                need = 1
            else:
                need = 0
            remaining_required = 0
            later = False
            for other in self._ail_actions:
                if other is action:
                    later = True
                    continue
                if not later or not other["positional"]:
                    continue
                if other["nargs"] is None:
                    remaining_required = remaining_required + 1
                elif isinstance(other["nargs"], int):
                    remaining_required = remaining_required + other["nargs"]
                elif other["nargs"] == ONE_OR_MORE:
                    remaining_required = remaining_required + 1
            available = len(positional_tokens) - pos_index
            if nargs is None or isinstance(nargs, int):
                take = need
            elif nargs == OPTIONAL:
                take = 1 if available > remaining_required else 0
            elif nargs == ONE_OR_MORE:
                take = available - remaining_required
                if take < 1:
                    take = 0
            else:
                take = available - remaining_required
                if take < 0:
                    take = 0
            raw = positional_tokens[pos_index:pos_index + take]
            pos_index = pos_index + take
            if len(raw) < need:
                continue
            self._ail_apply(namespace, action, raw, seen)
        if pos_index < len(positional_tokens):
            merged = []
            extra_index = 0
            token_index = pos_index
            while extra_index < len(extras) or token_index < len(positional_tokens):
                if token_index >= len(positional_tokens):
                    merged.append(extras[extra_index])
                    extra_index = extra_index + 1
                elif extra_index >= len(extras):
                    merged.append(positional_tokens[token_index])
                    token_index = token_index + 1
                elif extra_positions[extra_index] < positional_positions[token_index]:
                    merged.append(extras[extra_index])
                    extra_index = extra_index + 1
                else:
                    merged.append(positional_tokens[token_index])
                    token_index = token_index + 1
            extras = merged
        for action in self._ail_actions:
            if action in seen:
                continue
            default = action["default"]
            if default is None or default is SUPPRESS or not isinstance(default, str):
                continue
            if not hasattr(namespace, action["dest"]):
                continue
            if getattr(namespace, action["dest"]) is not default:
                continue
            namespace._ail_set(action["dest"], self._ail_coerce(action, default))
        missing = []
        for action in self._ail_actions:
            if action["required"] and action not in seen:
                missing.append(self._ail_arg_name(action))
            elif action["positional"] and action["nargs"] is None and action not in seen:
                missing.append(action["dest"])
            elif action["positional"] and action["nargs"] == ONE_OR_MORE and action not in seen:
                missing.append(action["dest"])
        if missing:
            self.error("the following arguments are required: " + ", ".join(missing))
        for group in self._ail_groups:
            found = []
            for action in seen:
                if action["group"] is group and action not in found:
                    found.append(action)
            if len(found) > 1:
                self.error("argument " + self._ail_arg_name(found[1]) + ": not allowed with argument " +
                           self._ail_arg_name(found[0]))
            if group._required and not found:
                self.error("one of the arguments " + " ".join([self._ail_arg_name(a) for a in group._actions]) +
                           " is required")
        return namespace, extras

    def parse_args(self, args=None, namespace=None):
        namespace, extras = self.parse_known_args(args, namespace)
        if extras:
            self.error("unrecognized arguments: " + " ".join(extras))
        return namespace
