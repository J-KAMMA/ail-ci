"""mdlite: convert a small Markdown subset to HTML.

Usage: mdlite [FILE]

The program reads Markdown from FILE (or standard input) and writes HTML to
standard output.  The supported subset is:

  * ATX headings, level 1 to 6
  * paragraphs separated by blank lines
  * inline emphasis, strong emphasis, code spans and links
  * fenced code blocks with an optional info string
  * bullet lists and ordered lists, with one level of nesting
  * block quotes, one level
  * horizontal rules
  * HTML escaping of &, <, > and " in text and code

Everything else is passed through as plain text.
"""

import sys


ESCAPES = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
}


def escape_char(char):
    """Return the HTML form of one character."""
    if char == "&":
        return "&amp;"
    if char == "<":
        return "&lt;"
    if char == ">":
        return "&gt;"
    if char == '"':
        return "&quot;"
    return char


def escape(text):
    """Escape a whole string for HTML text or attribute content."""
    out = []
    for char in text:
        out.append(escape_char(char))
    return "".join(out)


def heading_level(line):
    """Return 1..6 when the line is an ATX heading, else 0."""
    level = 0
    while level < len(line) and level < 6 and line[level] == "#":
        level += 1
    if level == 0:
        return 0
    if level < len(line) and line[level] != " ":
        return 0
    return level


def parse_item(line):
    """Return (indent, kind, content) for a list item line, else None.

    kind is "ul" for a bullet item and "ol" for an ordered item.
    """
    body = line.lstrip(" ")
    indent = len(line) - len(body)
    if not body:
        return None
    if body.startswith("- ") or body.startswith("* "):
        return (indent, "ul", body[2:].strip())
    if body == "-" or body == "*":
        return (indent, "ul", "")
    digits = 0
    while digits < len(body) and body[digits].isdigit():
        digits += 1
    if digits == 0:
        return None
    if digits == len(body) - 1 and body[digits] == ".":
        return (indent, "ol", "")
    if digits + 1 < len(body) and body[digits] == "." and body[digits + 1] == " ":
        return (indent, "ol", body[digits + 2:].strip())
    return None


def render_inline(text):
    """Render emphasis, code spans and links inside one block of text."""
    parts = []
    index = 0
    size = len(text)
    while index < size:
        char = text[index]
        if char == "`":
            end = text.find("`", index + 1)
            if end != -1:
                code = text[index + 1:end]
                parts.append("<code>" + escape(code) + "</code>")
                index = end + 1
            else:
                parts.append("`")
                index += 1
        elif char == "*":
            if text.startswith("**", index):
                end = text.find("**", index + 2)
                if end != -1:
                    inner = render_inline(text[index + 2:end])
                    parts.append("<strong>" + inner + "</strong>")
                    index = end + 2
                else:
                    parts.append("**")
                    index += 2
            else:
                end = text.find("*", index + 1)
                if end != -1:
                    inner = render_inline(text[index + 1:end])
                    parts.append("<em>" + inner + "</em>")
                    index = end + 1
                else:
                    parts.append("*")
                    index += 1
        elif char == "[":
            close = text.find("]", index + 1)
            if close != -1 and close + 1 < size and text[close + 1] == "(":
                end = text.find(")", close + 2)
                if end != -1:
                    label = text[index + 1:close]
                    target = text[close + 2:end]
                    parts.append('<a href="' + escape(target) + '">')
                    parts.append(render_inline(label))
                    parts.append("</a>")
                    index = end + 1
                else:
                    parts.append("[")
                    index += 1
            else:
                parts.append("[")
                index += 1
        else:
            parts.append(escape_char(char))
            index += 1
    return "".join(parts)


class ListItem:
    """One list item with its optional nested child items."""

    def __init__(self, content):
        self.content = content
        self.children = []


class Markdown:
    """A block parser that walks the input lines once and collects HTML."""

    def __init__(self, text, depth=0):
        self.lines = text.split("\n")
        self.depth = depth
        self.index = 0
        self.out = []

    def render(self):
        """Parse every line and return the finished HTML document text."""
        while self.index < len(self.lines):
            line = self.lines[self.index]
            if line.strip() == "":
                self.index += 1
                continue
            if self.is_fence(line):
                self.render_fence()
            elif heading_level(line):
                self.render_heading()
            elif line.strip() == "---":
                self.out.append("<hr>")
                self.index += 1
            elif self.depth == 0 and line.lstrip().startswith(">"):
                self.render_quote()
            elif parse_item(line) is not None:
                self.render_list()
            else:
                self.render_paragraph()
        text = "\n".join(self.out)
        if text:
            text += "\n"
        return text

    def is_fence(self, line):
        """True when the line opens or closes a fenced code block."""
        body = line.lstrip(" ")
        indent = len(line) - len(body)
        return indent <= 3 and body.startswith("```")

    def is_block_start(self, line):
        """True when a line would begin a new block, ending a paragraph."""
        if line.strip() == "":
            return True
        if heading_level(line):
            return True
        if self.is_fence(line):
            return True
        if line.strip() == "---":
            return True
        if self.depth == 0 and line.lstrip().startswith(">"):
            return True
        return parse_item(line) is not None

    def render_heading(self):
        """Render one ATX heading line."""
        line = self.lines[self.index]
        level = heading_level(line)
        content = line[level:].strip()
        self.out.append("<h" + str(level) + ">" + render_inline(content) + "</h" + str(level) + ">")
        self.index += 1

    def render_fence(self):
        """Render a fenced code block up to its closing fence or end of input."""
        line = self.lines[self.index]
        info = line.lstrip(" ")[3:].strip()
        self.index += 1
        code = []
        while self.index < len(self.lines):
            current = self.lines[self.index]
            if self.is_fence(current):
                self.index += 1
                break
            code.append(current)
            self.index += 1
        attribute = ""
        if info:
            language = info.split(" ")[0]
            attribute = ' class="language-' + escape(language) + '"'
        body = escape("\n".join(code))
        if code:
            body += "\n"
        self.out.append("<pre><code" + attribute + ">" + body + "</code></pre>")

    def render_paragraph(self):
        """Render consecutive text lines as one paragraph."""
        parts = []
        while self.index < len(self.lines):
            line = self.lines[self.index]
            if parts and self.is_block_start(line):
                break
            if line.strip() == "":
                break
            parts.append(line.strip())
            self.index += 1
        self.out.append("<p>" + render_inline(" ".join(parts)) + "</p>")

    def render_quote(self):
        """Render one block quote, one level deep."""
        inner = []
        while self.index < len(self.lines):
            line = self.lines[self.index]
            body = line.lstrip(" ")
            if not body.startswith(">"):
                break
            rest = body[1:]
            if rest.startswith(" "):
                rest = rest[1:]
            inner.append(rest)
            self.index += 1
        nested = Markdown("\n".join(inner), self.depth + 1).render()
        self.out.append("<blockquote>\n" + nested + "</blockquote>")

    def render_list(self):
        """Render a bullet or ordered list with at most one nesting level."""
        first = parse_item(self.lines[self.index])
        base = first[0]
        kind = first[1]
        top = []
        current = None
        while self.index < len(self.lines):
            item = parse_item(self.lines[self.index])
            if item is None:
                break
            indent, item_kind, content = item
            if indent <= base:
                if item_kind != kind or indent != base:
                    break
                current = ListItem(content)
                top.append(current)
            elif indent >= base + 2:
                if current is None:
                    break
                current.children.append(content)
            else:
                break
            self.index += 1
        lines = ["<" + kind + ">"]
        for item in top:
            if item.children:
                lines.append("<li>" + render_inline(item.content))
                lines.append("<" + kind + ">")
                for child in item.children:
                    lines.append("<li>" + render_inline(child) + "</li>")
                lines.append("</" + kind + ">")
                lines.append("</li>")
            else:
                lines.append("<li>" + render_inline(item.content) + "</li>")
        lines.append("</" + kind + ">")
        self.out.append("\n".join(lines))


def render(text):
    """Convert a Markdown string to HTML."""
    return Markdown(text).render()


def read_input(name):
    """Read the document from a file name, or from standard input."""
    if name is None:
        return sys.stdin.read()
    with open(name, "r", encoding="utf-8", errors="replace") as stream:
        return stream.read()


def main(argv):
    """Run the command line entry point and return the exit status."""
    name = None
    if len(argv) > 1:
        name = argv[1]
    try:
        text = read_input(name)
    except OSError:
        sys.stderr.write("mdlite: cannot open " + name + "\n")
        return 1
    sys.stdout.write(render(text))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
