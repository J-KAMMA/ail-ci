"""jsonpp.py [--indent N] [--sort-keys] [--compact] [--check] < input

A JSON pretty-printer and checker in plain Python 3, without `import json`.

The parser is recursive descent and builds a tree of tuples:

    ("obj", [(key, node), ...])   object, members in source order
    ("arr", [node, ...])          array
    ("str", text)                 string, already unescaped
    ("num", text)                 number, kept as its source text
    ("lit", "true"|"false"|"null")

Numbers are never converted, so a number beyond int64 is printed unchanged.

Output:
  * default: 2-space indent, one member per line, `": "` after keys;
  * --indent N: N spaces per level (N < 0 means newlines without indentation);
  * --sort-keys: members sorted by the byte order of the decoded key;
  * --compact: `,` and `:` with no spaces, on one line;
  * --check: print `ok <objects> <arrays> <strings> <numbers> <max_depth>`.
Strings are re-escaped the way `json.dumps(..., ensure_ascii=True)` does:
`\\uXXXX` for anything outside space..`~`, surrogate pairs above U+FFFF.

On a syntax error the program prints `error: line L col C: <message>` on
standard error and exits 1, with the position of the offending character.
"""

import sys


SPACES = " \t\n\r"
HEX = "0123456789abcdef"


class Parser:
    def __init__(self, text):
        self.text = text
        self.pos = 0
        self.objects = 0
        self.arrays = 0
        self.strings = 0
        self.numbers = 0
        self.max_depth = 0

    # -- errors -----------------------------------------------------------

    def fail(self, message):
        line = 1
        col = 1
        i = 0
        while i < self.pos and i < len(self.text):
            if self.text[i] == "\n":
                line += 1
                col = 1
            else:
                col += 1
            i += 1
        sys.stderr.write("error: line %d col %d: %s\n" % (line, col, message))
        sys.exit(1)

    # -- scanning ---------------------------------------------------------

    def skip_space(self):
        text = self.text
        while self.pos < len(text):
            ch = text[self.pos]
            if ch == " " or ch == "\t" or ch == "\n" or ch == "\r":
                self.pos += 1
            else:
                return

    def peek(self):
        if self.pos < len(self.text):
            return self.text[self.pos]
        return ""

    def hex_digit(self, ch):
        i = 0
        while i < 16:
            if HEX[i] == ch:
                return i
            i += 1
        return -1

    # -- values -----------------------------------------------------------

    def parse_value(self, level):
        self.skip_space()
        ch = self.peek()
        if ch == "":
            self.fail("Expecting value")
        if ch == "{":
            return self.parse_object(level)
        if ch == "[":
            return self.parse_array(level)
        if ch == '"':
            return ("str", self.parse_string())
        if ch == "t":
            return self.parse_literal("true", level)
        if ch == "f":
            return self.parse_literal("false", level)
        if ch == "n":
            return self.parse_literal("null", level)
        if ch == "-" or (ch >= "0" and ch <= "9"):
            return ("num", self.parse_number())
        self.fail("Expecting value")
        return ("lit", "null")

    def parse_literal(self, word, level):
        start = self.pos
        if self.text[start:start + len(word)] != word:
            self.fail("Expecting value")
        self.pos = start + len(word)
        return ("lit", word)

    def parse_number(self):
        start = self.pos
        text = self.text
        if self.peek() == "-":
            self.pos += 1
        ch = self.peek()
        if ch == "0":
            self.pos += 1
        elif ch >= "1" and ch <= "9":
            while self.pos < len(text):
                ch = text[self.pos]
                if ch >= "0" and ch <= "9":
                    self.pos += 1
                else:
                    break
        else:
            self.fail("Expecting value")
        if self.peek() == ".":
            self.pos += 1
            ch = self.peek()
            if not (ch >= "0" and ch <= "9"):
                self.fail("Expecting digit after decimal point")
            while self.pos < len(text):
                ch = text[self.pos]
                if ch >= "0" and ch <= "9":
                    self.pos += 1
                else:
                    break
        ch = self.peek()
        if ch == "e" or ch == "E":
            self.pos += 1
            ch = self.peek()
            if ch == "+" or ch == "-":
                self.pos += 1
            ch = self.peek()
            if not (ch >= "0" and ch <= "9"):
                self.fail("Expecting digit in exponent")
            while self.pos < len(text):
                ch = text[self.pos]
                if ch >= "0" and ch <= "9":
                    self.pos += 1
                else:
                    break
        self.numbers += 1
        return text[start:self.pos]

    def parse_string(self):
        text = self.text
        self.pos += 1
        out = []
        while True:
            if self.pos >= len(text):
                self.fail("Unterminated string starting at")
            ch = text[self.pos]
            self.pos += 1
            if ch == '"':
                break
            if ch == "\\":
                if self.pos >= len(text):
                    self.fail("Unterminated string starting at")
                esc = text[self.pos]
                self.pos += 1
                if esc == '"':
                    out.append('"')
                elif esc == "\\":
                    out.append("\\")
                elif esc == "/":
                    out.append("/")
                elif esc == "b":
                    out.append("\b")
                elif esc == "f":
                    out.append("\f")
                elif esc == "n":
                    out.append("\n")
                elif esc == "r":
                    out.append("\r")
                elif esc == "t":
                    out.append("\t")
                elif esc == "u":
                    out.append(self.parse_unicode_escape())
                else:
                    self.pos -= 1
                    self.fail("Invalid \\escape")
            elif ord(ch) < 0x20:
                self.pos -= 1
                self.fail("Invalid control character")
            else:
                out.append(ch)
        self.strings += 1
        return "".join(out)

    def parse_unicode_escape(self):
        start = self.pos
        code = 0
        i = 0
        while i < 4:
            if self.pos >= len(self.text):
                self.fail("Invalid \\uXXXX escape")
            digit = self.hex_digit(self.text[self.pos])
            if digit < 0:
                self.fail("Invalid \\uXXXX escape")
            code = code * 16 + digit
            self.pos += 1
            i += 1
        return chr(code)

    def parse_array(self, level):
        self.arrays += 1
        if level > self.max_depth:
            self.max_depth = level
        self.pos += 1
        items = []
        self.skip_space()
        if self.peek() == "]":
            self.pos += 1
            return ("arr", items)
        while True:
            items.append(self.parse_value(level + 1))
            self.skip_space()
            ch = self.peek()
            if ch == ",":
                self.pos += 1
                continue
            if ch == "]":
                self.pos += 1
                return ("arr", items)
            self.fail("Expecting ',' delimiter")

    def parse_object(self, level):
        self.objects += 1
        if level > self.max_depth:
            self.max_depth = level
        self.pos += 1
        members = []
        self.skip_space()
        if self.peek() == "}":
            self.pos += 1
            return ("obj", members)
        while True:
            self.skip_space()
            if self.peek() != '"':
                self.fail("Expecting property name enclosed in double quotes")
            key = self.parse_string()
            self.skip_space()
            if self.peek() != ":":
                self.fail("Expecting ':' delimiter")
            self.pos += 1
            value = self.parse_value(level + 1)
            members.append((key, value))
            self.skip_space()
            ch = self.peek()
            if ch == ",":
                self.pos += 1
                continue
            if ch == "}":
                self.pos += 1
                return ("obj", members)
            self.fail("Expecting ',' delimiter")


def sort_members(members):
    """Merge sort members by the byte order of the decoded key."""
    if len(members) < 2:
        return members
    middle = len(members) // 2
    left = sort_members(members[:middle])
    right = sort_members(members[middle:])
    out = []
    i = 0
    j = 0
    while i < len(left) and j < len(right):
        if left[i][0].encode("utf-8") <= right[j][0].encode("utf-8"):
            out.append(left[i])
            i += 1
        else:
            out.append(right[j])
            j += 1
    while i < len(left):
        out.append(left[i])
        i += 1
    while j < len(right):
        out.append(right[j])
        j += 1
    return out


def sort_node(node):
    if node[0] == "obj":
        members = node[1]
        i = 0
        while i < len(members):
            members[i] = (members[i][0], sort_node(members[i][1]))
            i += 1
        return ("obj", sort_members(members))
    if node[0] == "arr":
        items = node[1]
        i = 0
        while i < len(items):
            items[i] = sort_node(items[i])
            i += 1
        return ("arr", items)
    return node


def hex4(code):
    return HEX[(code >> 12) & 15] + HEX[(code >> 8) & 15] + HEX[(code >> 4) & 15] + HEX[code & 15]


def escape_string(value):
    out = []
    for ch in value:
        code = ord(ch)
        if ch == '"':
            out.append('\\"')
        elif ch == "\\":
            out.append("\\\\")
        elif ch == "\b":
            out.append("\\b")
        elif ch == "\f":
            out.append("\\f")
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\r":
            out.append("\\r")
        elif ch == "\t":
            out.append("\\t")
        elif code < 0x20 or code > 0x7E:
            if code >= 0x10000:
                v = code - 0x10000
                out.append("\\u" + hex4(0xD800 + (v >> 10)))
                out.append("\\u" + hex4(0xDC00 + (v & 0x3FF)))
            else:
                out.append("\\u" + hex4(code))
        else:
            out.append(ch)
    return "".join(out)


def emit(node, level, indent, compact, out):
    kind = node[0]
    if kind == "str":
        out.append('"' + escape_string(node[1]) + '"')
        return
    if kind == "num":
        out.append(node[1])
        return
    if kind == "lit":
        out.append(node[1])
        return
    if kind == "arr":
        items = node[1]
        if not items:
            out.append("[]")
            return
        out.append("[")
        i = 0
        while i < len(items):
            if i > 0:
                out.append(",")
            if not compact:
                out.append("\n")
                out.append(" " * (indent * (level + 1)))
            emit(items[i], level + 1, indent, compact, out)
            i += 1
        if not compact:
            out.append("\n")
            out.append(" " * (indent * level))
        out.append("]")
        return
    members = node[1]
    if not members:
        out.append("{}")
        return
    out.append("{")
    i = 0
    while i < len(members):
        if i > 0:
            out.append(",")
        if not compact:
            out.append("\n")
            out.append(" " * (indent * (level + 1)))
        out.append('"' + escape_string(members[i][0]) + '"')
        if compact:
            out.append(":")
        else:
            out.append(": ")
        emit(members[i][1], level + 1, indent, compact, out)
        i += 1
    if not compact:
        out.append("\n")
        out.append(" " * (indent * level))
    out.append("}")


def usage_error(message):
    sys.stderr.write("jsonpp.py: %s\n" % message)
    sys.stderr.write("usage: jsonpp.py [--indent N] [--sort-keys] [--compact] [--check]\n")
    sys.exit(2)


def parse_count(text):
    """Parse a non-negative decimal option value without overflowing int64."""
    if text == "":
        usage_error("--indent needs a number")
    i = 0
    value = 0
    while i < len(text):
        ch = text[i]
        if ch < "0" or ch > "9":
            usage_error("--indent needs a number")
        if value > 100000:
            usage_error("--indent is too large")
        value = value * 10 + (ord(ch) - 48)
        i += 1
    return value


def main():
    indent = 2
    sort_keys = False
    compact = False
    check = False
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--indent":
            if i + 1 >= len(args):
                usage_error("--indent needs a number")
            indent = parse_count(args[i + 1])
            i += 2
        elif arg == "--sort-keys":
            sort_keys = True
            i += 1
        elif arg == "--compact":
            compact = True
            i += 1
        elif arg == "--check":
            check = True
            i += 1
        else:
            usage_error("unknown option %s" % arg)
    if compact:
        indent = 0
    text = sys.stdin.read()
    parser = Parser(text)
    node = parser.parse_value(1)
    parser.skip_space()
    if parser.pos < len(text):
        parser.fail("Extra data")
    if sort_keys:
        node = sort_node(node)
    if check:
        sys.stdout.write("ok %d %d %d %d %d\n"
                         % (parser.objects, parser.arrays, parser.strings,
                            parser.numbers, parser.max_depth))
    else:
        out = []
        emit(node, 0, indent, compact, out)
        out.append("\n")
        sys.stdout.write("".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
