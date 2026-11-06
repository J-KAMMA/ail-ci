#!/usr/bin/env python3
"""Render the Markdown under ``docs/`` as a self-contained static site.

Usage:
    python3 tools/docs_site.py docs -o site/

Only the Python standard library is used.  The converter handles the subset the docs
actually use: ATX and setext headings with GitHub-style ids, fenced code blocks with a
``language-*`` class, tables (including alignment and escaped ``|``), ordered and
unordered lists (nested, with task boxes), block quotes, horizontal rules, paragraphs,
links and images, inline code, emphasis, strikethrough, autolinks, backslash escapes,
and HTML comments.  A construct the converter cannot represent is printed as
``unconverted: docs/FILE:LINE: reason`` and makes the command exit 1; it is never
silently dropped.

The output has one page per Markdown file (mirroring the directory tree with a ``.html``
suffix), a generated ``index.html`` when ``docs/index.md`` does not exist, a sidebar
built from the file tree, ``search-index.json``, and an inline search/theme script plus
inline CSS with light and dark palettes.  No font or script is loaded from another host.

A relative link that points outside ``docs/`` but inside the repository is published
under ``_repo/`` with the same relative path (Markdown as HTML, other files verbatim) and
rewritten to that copy, so the built site never links outside its own root.  A link that
leaves the repository is reported as an unconverted construct and exits 1.

Publishing with GitHub Pages (owner approval and a workflow edit are required, so this
tool does not do it): commit the generated ``site/`` directory on a ``gh-pages`` branch
(or an ``/docs`` directory chosen in the repository settings), then in the repository
Settings -> Pages set "Build and deployment" to "Deploy from a branch", choose that
branch and ``/ (root)``, and save.  Alternatively, after the owner approves a workflow
change, add a job that runs ``python3 tools/docs_site.py docs -o site`` on the default
branch and uploads ``site/`` with ``actions/upload-pages-artifact`` followed by
``actions/deploy-pages``; grant the job ``pages: write`` and ``id-token: write`` and
protect the ``github-pages`` environment.  Do not put generated files on ``main``.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import posixpath
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import unquote

SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
FENCE_RE = re.compile(r"^(?P<indent> {0,3})(?P<fence>`{3,}|~{3,})(?P<info>.*)$")
ATX_RE = re.compile(r"^ {0,3}(?P<hashes>#{1,6})(?:[ \t]+(?P<text>.*?))?[ \t]*$")
SETEXT_RE = re.compile(r"^ {0,3}(?P<mark>=+|-+)[ \t]*$")
HR_RE = re.compile(r"^ {0,3}(?:(?:\*[ \t]*){3,}|(?:-[ \t]*){3,}|(?:_[ \t]*){3,})$")
LIST_RE = re.compile(r"^(?P<indent> *)(?P<marker>[-+*]|\d+[.)])(?P<spaces>[ \t]+)(?P<text>.*)$")
BLOCKQUOTE_RE = re.compile(r"^ {0,3}> ?(?P<text>.*)$")
REF_DEF_RE = re.compile(r"^ {0,3}\[[^\]]+\]:[ \t]*\S")
ESCAPE_RE = re.compile(r"\\([\\`*{}\[\]()#+\-.!_>~|])")
CODE_RE = re.compile(r"(`+)(.+?)\1", re.S)
COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
LINK_START_RE = re.compile(r"!?\[([^\]]*)\]\(")
AUTOLINK_RE = re.compile(r"<((?:https?|mailto):[^>]+)>", re.I)
RAW_TAG_RE = re.compile(r"</?[A-Za-z][^>]*>")
REF_LINK_RE = re.compile(r"!?\[[^\]]*\]\[[^\]]*\]")


def escape(text, quote=False):
    return html.escape(text, quote=quote)


def plain_inline(text):
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    spans = []

    def protect(match):
        spans.append(match.group(2))
        return "\x00%d\x00" % (len(spans) - 1)

    text = CODE_RE.sub(protect, text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\*\*(?=\S)(.+?)(?<=\S)\*\*", r"\1", text, flags=re.S)
    text = re.sub(r"__(?=\S)(.+?)(?<=\S)__", r"\1", text, flags=re.S)
    text = re.sub(r"~~(?=\S)(.+?)(?<=\S)~~", r"\1", text, flags=re.S)
    text = re.sub(r"(?<![*\w])\*(?=\S)(.+?)(?<=\S)\*(?![*\w])", r"\1", text, flags=re.S)
    text = re.sub(r"(?<![_\w])_(?=\S)(.+?)(?<=\S)_(?![_\w])", r"\1", text, flags=re.S)
    text = ESCAPE_RE.sub(r"\1", text)
    return re.sub(r"\x00(\d+)\x00", lambda match: spans[int(match.group(1))], text)


def slugify(text):
    value = plain_inline(text).strip().lower()
    value = re.sub(r"[^\w\s-]", "", value, flags=re.UNICODE)
    value = re.sub(r"\s", "-", value)
    return value or "section"


class Slugger:
    def __init__(self):
        self.occurrences = {}

    def slug(self, text):
        result = slugify(text)
        original = result
        while result in self.occurrences:
            self.occurrences[original] += 1
            result = "%s-%d" % (original, self.occurrences[original])
        self.occurrences[result] = 0
        return result


def split_table_row(line):
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|") and not line.endswith("\\|"):
        line = line[:-1]
    cells = []
    current = []
    index = 0
    code_run = 0
    while index < len(line):
        char = line[index]
        if char == "\\" and index + 1 < len(line) and line[index + 1] == "|":
            current.append("|")
            index += 2
            continue
        if char == "`":
            run = index
            while run < len(line) and line[run] == "`":
                run += 1
            length = run - index
            if code_run == 0:
                code_run = length
            elif code_run == length:
                code_run = 0
            current.append(line[index:run])
            index = run
            continue
        if char == "|" and code_run == 0:
            cells.append("".join(current).strip())
            current = []
            index += 1
            continue
        current.append(char)
        index += 1
    cells.append("".join(current).strip())
    return cells


def is_table_delimiter(line):
    if "|" not in line:
        return False
    cells = split_table_row(line)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


def table_align(cell):
    left = cell.startswith(":")
    right = cell.endswith(":")
    if left and right:
        return "center"
    if right:
        return "right"
    if left:
        return "left"
    return ""


def first_heading(path):
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    fence = None
    comment = False
    for index, raw in enumerate(lines):
        if fence is not None:
            char, length = fence
            if re.match(r"^ {0,3}%s{%d,}[ \t]*$" % (re.escape(char), length), raw):
                fence = None
            continue
        found = FENCE_RE.match(raw)
        if found:
            marks = found.group("fence")
            fence = (marks[0], len(marks))
            continue
        if comment:
            if "-->" in raw:
                comment = False
            continue
        if "<!--" in raw:
            if "-->" not in raw.split("<!--", 1)[1]:
                comment = True
            continue
        found = ATX_RE.match(raw)
        if found:
            return plain_inline(found.group("text") or "").strip()
        if (index + 1 < len(lines) and raw.strip() and not raw.startswith("    ")
                and SETEXT_RE.match(lines[index + 1])):
            return plain_inline(raw.strip()).strip()
    return ""


class InlineRenderer:
    def __init__(self, rewrite_href=None, warn=None):
        self.rewrite_href = rewrite_href or (lambda value, line=None: value)
        self.warn = warn or (lambda message: None)

    def _destination(self, line, start):
        index = start
        while index < len(line) and line[index] in " \t":
            index += 1
        if index < len(line) and line[index] == "<":
            end = line.find(">", index + 1)
            if end < 0:
                return None, len(line)
            return line[index + 1:end], end + 1
        begin = index
        depth = 0
        while index < len(line):
            char = line[index]
            if char == "\\" and index + 1 < len(line):
                index += 2
                continue
            if char == "(":
                depth += 1
            elif char == ")":
                if depth == 0:
                    break
                depth -= 1
            elif char in " \t" and depth == 0:
                break
            index += 1
        return line[begin:index], index

    def _replace_links(self, text, token, resolve, render_label, line=None):
        pieces = []
        position = 0
        while True:
            match = LINK_START_RE.search(text, position)
            if not match:
                pieces.append(text[position:])
                break
            image = text[match.start()] == "!"
            target, end = self._destination(text, match.end())
            if target is None:
                pieces.append(text[position:match.end()])
                position = match.end()
                continue
            cursor = end
            while cursor < len(text) and text[cursor] in " \t":
                cursor += 1
            if cursor < len(text) and text[cursor] in "\"'(":
                quote = text[cursor]
                close = ")" if quote == "(" else quote
                stop = text.find(close, cursor + 1)
                if stop < 0:
                    pieces.append(text[position:match.end()])
                    position = match.end()
                    continue
                cursor = stop + 1
                while cursor < len(text) and text[cursor] in " \t":
                    cursor += 1
            if cursor >= len(text) or text[cursor] != ")":
                pieces.append(text[position:match.end()])
                position = match.end()
                continue
            label = match.group(1)
            href = self.rewrite_href(
                target, (line + text.count("\n", 0, match.start())) if line else None)
            if image:
                value = '<img src="%s" alt="%s" loading="lazy">' % (
                    escape(href, True), escape(plain_inline(resolve(label)), True))
            else:
                value = '<a href="%s">%s</a>' % (
                    escape(href, True), render_label(label))
            pieces.append(text[position:match.start()])
            pieces.append(token(value))
            position = cursor + 1
        return "".join(pieces)

    def _code_tokens(self, text, token):
        pieces = []
        index = 0
        while index < len(text):
            if text[index] != "`":
                pieces.append(text[index])
                index += 1
                continue
            run = index
            while run < len(text) and text[run] == "`":
                run += 1
            marker = text[index:run]
            stop = text.find(marker, run)
            if stop < 0:
                pieces.append(text[index:run])
                index = run
                continue
            body = text[run:stop]
            if body.startswith(" ") and body.endswith(" ") and body.strip():
                body = body[1:-1]
            pieces.append(token("<code>%s</code>" % escape(body)))
            index = stop + len(marker)
        return "".join(pieces)

    def _emphasis(self, text):
        text = re.sub(r"\*\*(?=\S)(.+?)(?<=\S)\*\*", r"<strong>\1</strong>", text, flags=re.S)
        text = re.sub(r"__(?=\S)(.+?)(?<=\S)__", r"<strong>\1</strong>", text, flags=re.S)
        text = re.sub(r"~~(?=\S)(.+?)(?<=\S)~~", r"<del>\1</del>", text, flags=re.S)
        text = re.sub(r"(?<![*\w])\*(?=\S)(.+?)(?<=\S)\*(?![*\w])",
                      r"<em>\1</em>", text, flags=re.S)
        text = re.sub(r"(?<![_\w])_(?=\S)(.+?)(?<=\S)_(?![_\w])",
                      r"<em>\1</em>", text, flags=re.S)
        return text

    def render(self, text, line=None):
        tokens = []

        def token(value):
            tokens.append(value)
            return "\x00%d\x00" % (len(tokens) - 1)

        text = COMMENT_RE.sub("", text)
        text = ESCAPE_RE.sub(lambda m: token(escape(m.group(1))), text)
        text = self._code_tokens(text, token)
        def resolve_tokens(value):
            while "\x00" in value:
                replaced = re.sub(r"\x00(\d+)\x00",
                                  lambda m: tokens[int(m.group(1))], value)
                if replaced == value:
                    break
                value = replaced
            return value

        def render_label(value):
            protected = re.sub(r"\x00(\d+)\x00",
                               lambda m: "\x01%s\x01" % m.group(1), value)
            rendered = self.render(protected, line)
            return re.sub(r"\x01(\d+)\x01",
                          lambda m: tokens[int(m.group(1))], rendered)

        text = self._replace_links(text, token, resolve_tokens, render_label, line)
        text = AUTOLINK_RE.sub(
            lambda m: token('<a href="%s">%s</a>' % (escape(m.group(1), True),
                                                      escape(m.group(1)))), text)
        text = escape(text, quote=False)
        text = re.sub(r" {2,}\n", "<br>\n", text)
        text = self._emphasis(text)

        def restore(match):
            return tokens[int(match.group(1))]

        while "\x00" in text:
            replaced = re.sub(r"\x00(\d+)\x00", restore, text)
            if replaced == text:
                break
            text = replaced
        return text.replace("\x00", "")


class PageRenderer:
    def __init__(self, src, docs_root, html_rel, warnings, code_blocks,
                 repo_root=None, external=None, external_mode=False):
        self.src = src
        self.docs_root = docs_root
        self.repo_root = repo_root or docs_root.parent
        self.external = external if external is not None else {}
        self.external_mode = external_mode
        self.html_rel = html_rel
        self.warnings = warnings
        self.code_blocks = code_blocks
        self.slugger = Slugger()
        self.headings = []
        self.inline = InlineRenderer(self.rewrite_href)

    def warn(self, line, message):
        try:
            name = self.src.relative_to(self.docs_root)
        except ValueError:
            name = self.src.relative_to(self.repo_root)
        self.warnings.append("%s:%d: %s" % (name, line, message))

    def rewrite_href(self, destination, line=None):
        if not destination or destination.startswith(("#", "//")) or SCHEME_RE.match(destination):
            return destination
        path_part = destination
        suffix = ""
        if "#" in path_part:
            path_part, fragment = path_part.split("#", 1)
            suffix = "#" + fragment
        if "?" in path_part:
            path_part, query = path_part.split("?", 1)
            suffix = "?" + query + suffix
        if path_part.startswith("/"):
            return destination
        target = Path(os.path.normpath(str(self.src.parent / unquote(path_part))))
        if not target.exists():
            self.warn(line or 0, "relative link %r: target %s does not exist"
                      % (destination, target))
            return destination
        if target.is_dir():
            for name in ("index.md", "README.md"):
                index = target / name
                if index.is_file():
                    target = index
                    break
        start = posixpath.dirname(self.html_rel.as_posix()) or "."
        try:
            rel = target.relative_to(self.docs_root)
            external = False
        except ValueError:
            try:
                rel = target.relative_to(self.repo_root)
            except ValueError:
                self.warn(line or 0,
                          "relative link %r leaves the repository; not published"
                          % destination)
                return destination
            external = True
        if external:
            if target.is_dir():
                published = Path("_repo") / rel / "index.html"
                self.external[rel] = "dir"
            elif target.suffix.lower() in (".md", ".markdown"):
                published = Path("_repo") / rel.with_suffix(".html")
                self.external[rel] = "markdown"
            else:
                published = Path("_repo") / rel
                self.external[rel] = "copy"
            return posixpath.relpath(published.as_posix(), start) + suffix
        if target.is_dir():
            return destination
        if target.suffix.lower() in (".md", ".markdown"):
            rel = rel.with_suffix(".html")
        return posixpath.relpath(rel.as_posix(), start) + suffix

    def _warn_inline(self, text, line):
        visible = CODE_RE.sub("", COMMENT_RE.sub("", text))
        if REF_LINK_RE.search(visible):
            self.warn(line, "reference-style link is not supported")
        elif REF_DEF_RE.match(visible):
            self.warn(line, "reference link definition is not supported")
        if self.external_mode:
            return
        for match in RAW_TAG_RE.finditer(visible):
            if not re.match(r"<(?:https?|mailto):", match.group(0), re.I):
                self.warn(line, "raw HTML %r is not converted" % match.group(0))
                break

    def _starts_block(self, lines, index):
        line = lines[index][1]
        if not line.strip():
            return True
        if (FENCE_RE.match(line) or ATX_RE.match(line) or HR_RE.match(line)
                or BLOCKQUOTE_RE.match(line) or line.lstrip().startswith("<!--")
                or line.startswith("    ")):
            return True
        found = LIST_RE.match(line)
        if found and len(found.group("indent")) <= 3:
            return True
        if "|" in line and index + 1 < len(lines) and is_table_delimiter(lines[index + 1][1]):
            return True
        return False

    def render(self, text):
        lines = [(number, line) for number, line in
                 enumerate(text.splitlines(), 1)]
        return self.parse_blocks(lines)

    def parse_blocks(self, lines):
        out = []
        index = 0
        total = len(lines)
        while index < total:
            number, line = lines[index]
            if not line.strip():
                index += 1
                continue
            if line.lstrip().startswith("<!--"):
                rest = line.split("<!--", 1)[1]
                while "-->" not in rest and index + 1 < total:
                    index += 1
                    rest = lines[index][1]
                if "-->" not in rest:
                    self.warn(number, "unclosed HTML comment")
                index += 1
                continue
            found = FENCE_RE.match(line)
            if found:
                rendered, index = self._fence(lines, index, found)
                out.append(rendered)
                continue
            found = ATX_RE.match(line)
            if found:
                level = len(found.group("hashes"))
                text = found.group("text") or ""
                slug = self.slugger.slug(text)
                self.headings.append((level, plain_inline(text).strip(), slug))
                self._warn_inline(text, number)
                out.append('<h%d id="%s">%s</h%d>' % (level, escape(slug, True),
                                                       self.inline.render(text, number), level))
                index += 1
                continue
            if (index + 1 < total and line.strip() and not line.startswith("    ")
                    and SETEXT_RE.match(lines[index + 1][1])):
                level = 1 if lines[index + 1][1].strip().startswith("=") else 2
                text = line.strip()
                slug = self.slugger.slug(text)
                self.headings.append((level, plain_inline(text).strip(), slug))
                self._warn_inline(text, number)
                out.append('<h%d id="%s">%s</h%d>' % (level, escape(slug, True),
                                                       self.inline.render(text, number), level))
                index += 2
                continue
            if HR_RE.match(line):
                out.append("<hr>")
                index += 1
                continue
            if BLOCKQUOTE_RE.match(line):
                inner = []
                while index < total:
                    found = BLOCKQUOTE_RE.match(lines[index][1])
                    if not found:
                        break
                    inner.append((lines[index][0], found.group("text")))
                    index += 1
                out.append("<blockquote>\n%s\n</blockquote>" % self.parse_blocks(inner))
                continue
            found = LIST_RE.match(line)
            if found and len(found.group("indent")) <= 3:
                rendered, index = self._list(lines, index)
                out.append(rendered)
                continue
            if "|" in line and index + 1 < total and is_table_delimiter(lines[index + 1][1]):
                rendered, index = self._table(lines, index)
                out.append(rendered)
                continue
            if line.startswith("    "):
                body = []
                while index < total:
                    current = lines[index][1]
                    if not current.strip():
                        body.append("")
                        index += 1
                        continue
                    if not current.startswith("    "):
                        break
                    body.append(current[4:])
                    index += 1
                while body and not body[-1]:
                    body.pop()
                out.append("<pre><code>%s</code></pre>" % escape("\n".join(body)))
                continue
            if line.lstrip().startswith("<") and not self.external_mode:
                self.warn(number, "raw HTML block is not converted")
            start = index
            chunk = []
            while index < total:
                current = lines[index][1]
                if index > start and self._starts_block(lines, index):
                    break
                if index > start and not current.strip():
                    break
                chunk.append(current)
                index += 1
            text = "\n".join(chunk).strip()
            self._warn_inline(text, number)
            out.append("<p>%s</p>" % self.inline.render(text, number))
        return "\n".join(out)

    def _fence(self, lines, index, found):
        number = lines[index][0]
        marks = found.group("fence")
        char = marks[0]
        length = len(marks)
        indent = len(found.group("indent"))
        info = found.group("info").strip()
        body = []
        index += 1
        closed = False
        close_re = re.compile(r"^ {0,3}%s{%d,}[ \t]*$" % (re.escape(char), length))
        while index < len(lines):
            line = lines[index][1]
            if close_re.match(line):
                closed = True
                index += 1
                break
            strip = min(indent, len(line) - len(line.lstrip(" ")))
            body.append(line[strip:])
            index += 1
        if not closed:
            self.warn(number, "unclosed fenced code block")
        if info.startswith("{"):
            inside = info.strip("{}").strip()
            language = inside.lstrip(".")
        else:
            language = info.split()[0] if info else ""
        language = re.sub(r"[^A-Za-z0-9_-]", "-", language)
        self.code_blocks[0] += 1
        cls = ' class="language-%s"' % escape(language, True) if language else ""
        return "<pre><code%s>%s</code></pre>" % (cls, escape("\n".join(body))), index

    def _list(self, lines, index):
        first = LIST_RE.match(lines[index][1])
        base = len(first.group("indent"))
        ordered = first.group("marker")[0].isdigit()
        start_number = int(re.match(r"\d+", first.group("marker")).group(0)) if ordered else 1
        items = []
        while index < len(lines):
            found = LIST_RE.match(lines[index][1])
            if (not found or len(found.group("indent")) != base
                    or found.group("marker")[0].isdigit() != ordered):
                break
            content_column = found.start("text")
            item_lines = [(lines[index][0], found.group("text"))]
            item_number = (int(re.match(r"\d+", found.group("marker")).group(0))
                           if ordered else 1)
            index += 1
            pending = []
            while index < len(lines):
                current = lines[index][1]
                if not current.strip():
                    pending.append((lines[index][0], ""))
                    index += 1
                    continue
                nested = LIST_RE.match(current)
                indent = len(current) - len(current.lstrip(" "))
                if nested and len(nested.group("indent")) <= base:
                    break
                if indent >= content_column:
                    item_lines.extend(pending)
                    pending = []
                    item_lines.append((lines[index][0], current[content_column:]))
                    index += 1
                    continue
                if nested and len(nested.group("indent")) > base:
                    item_lines.extend(pending)
                    pending = []
                    cut = min(len(nested.group("indent")), content_column)
                    item_lines.append((lines[index][0], current[cut:]))
                    index += 1
                    continue
                break
            task = None
            if item_lines:
                first_line = item_lines[0][1]
                task_match = re.match(r"\[([ xX])\][ \t]+(.*)$", first_line)
                if task_match:
                    task = task_match.group(1).lower() == "x"
                    item_lines[0] = (item_lines[0][0], task_match.group(2))
            inner = self.parse_blocks(item_lines)
            if task is not None:
                box = '<input type="checkbox" disabled%s> ' % (" checked" if task else "")
                items.append('<li class="task">%s%s</li>' % (box, inner))
            else:
                items.append("<li>%s</li>" % inner)
        if ordered:
            attr = ' start="%d"' % start_number if start_number != 1 else ""
            tag = "ol"
        else:
            attr = ""
            tag = "ul"
        return "<%s%s>\n%s\n</%s>" % (tag, attr, "\n".join(items), tag), index

    def _table(self, lines, index):
        header = split_table_row(lines[index][1])
        delimiter = split_table_row(lines[index + 1][1])
        number = lines[index][0]
        if len(header) != len(delimiter):
            self.warn(number, "table header and delimiter have different cell counts")
        aligns = [table_align(cell) for cell in delimiter]
        index += 2
        rows = []
        while index < len(lines):
            if (index + 1 < len(lines) and "|" in lines[index][1]
                    and is_table_delimiter(lines[index + 1][1])):
                break
            row_text = lines[index][1]
            if "|" not in row_text:
                break
            index += 1
            while not row_text.rstrip().endswith("|") and index < len(lines):
                continuation = lines[index][1]
                if not continuation.strip():
                    look = index + 1
                    while look < len(lines) and not lines[look][1].strip():
                        look += 1
                    if (look < len(lines) and lines[look][1].rstrip().endswith("|")
                            and not self._starts_block(lines, look)):
                        row_text += "\n" + continuation
                        index += 1
                        continue
                    break
                if self._starts_block(lines, index):
                    break
                row_text += "\n" + continuation
                index += 1
            if "|" not in row_text:
                break
            rows.append(split_table_row(row_text))
            if index < len(lines) and not lines[index][1].strip():
                break

        width = max([len(header)] + [len(row) for row in rows])
        while len(header) < width:
            header.append("")
        for row in rows:
            while len(row) < width:
                row.append("")
        while len(aligns) < width:
            aligns.append("")

        def cell_html(tag, text, align):
            style = ' style="text-align:%s"' % align if align else ""
            return "<%s%s>%s</%s>" % (tag, style, self.inline.render(text, number), tag)

        head = "<tr>%s</tr>" % "".join(
            cell_html("th", text, aligns[pos] if pos < len(aligns) else "")
            for pos, text in enumerate(header))
        body = "\n".join(
            "<tr>%s</tr>" % "".join(
                cell_html("td", text, aligns[pos] if pos < len(aligns) else "")
                for pos, text in enumerate(row))
            for row in rows)
        parts = ['<div class="table-wrap"><table>', "<thead>%s</thead>" % head]
        if body:
            parts.append("<tbody>\n%s\n</tbody>" % body)
        parts.append("</table></div>")
        return "\n".join(parts), index


CSS = """
:root{--bg:#ffffff;--fg:#1d2433;--muted:#5b6475;--line:#d9dee8;--panel:#f5f7fb;
--accent:#1256a8;--code:#f2f5fa;--mark:#fff3cd;--shadow:0 1px 2px rgba(16,24,40,.08)}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
--bg:#10151d;--fg:#e6ebf3;--muted:#a3adbd;--line:#2b3444;--panel:#161d28;
--accent:#7ab7ff;--code:#171f2b;--mark:#4a3d12;--shadow:none}}
html[data-theme="dark"]{--bg:#10151d;--fg:#e6ebf3;--muted:#a3adbd;--line:#2b3444;
--panel:#161d28;--accent:#7ab7ff;--code:#171f2b;--mark:#4a3d12;--shadow:none}
*{box-sizing:border-box}
html{color-scheme:light dark}
body{margin:0;background:var(--bg);color:var(--fg);line-height:1.58;
font-family:system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
font-size:16px}
a{color:var(--accent);text-decoration-thickness:.08em;text-underline-offset:.15em}
a:hover{text-decoration-thickness:.14em}
.skip{position:absolute;left:-999px;top:0;background:var(--bg);padding:.5rem;z-index:10}
.skip:focus{left:.5rem;top:.5rem}
.layout{display:grid;grid-template-columns:19rem minmax(0,1fr);gap:2.5rem;
max-width:86rem;margin:0 auto;padding:0 1.25rem 4rem}
.sidebar{position:sticky;top:0;max-height:100vh;overflow:auto;padding:1.2rem 0 2rem;
border-right:1px solid var(--line);padding-right:1.2rem}
.brand{display:block;font-weight:700;font-size:1.15rem;margin-bottom:.8rem;
color:var(--fg);text-decoration:none}
.search{width:100%;padding:.5rem .65rem;margin:.2rem 0 .9rem;border:1px solid var(--line);
border-radius:.45rem;background:var(--bg);color:var(--fg);font:inherit}
#search-results{font-size:.9rem;margin:0 0 .8rem}
#search-results a{display:block;padding:.25rem 0}
nav ul{list-style:none;margin:0;padding:0 0 0 .55rem}
nav li{margin:.1rem 0}
nav a{display:block;padding:.16rem .25rem;border-radius:.3rem;text-decoration:none;
color:var(--muted);font-size:.94rem}
nav a:hover,nav a[aria-current="page"]{background:var(--panel);color:var(--fg)}
.group-title{margin:.9rem 0 .25rem;font-size:.76rem;letter-spacing:.06em;
text-transform:uppercase;color:var(--muted)}
.theme{margin:.5rem 0 1rem;padding:.35rem .6rem;border:1px solid var(--line);
border-radius:.4rem;background:var(--panel);color:var(--fg);cursor:pointer;font:inherit}
main{min-width:0;padding-top:1.2rem}
article{max-width:62rem}
h1,h2,h3,h4,h5,h6{line-height:1.25;margin:1.8rem 0 .65rem;scroll-margin-top:1rem}
h1{font-size:2.05rem;margin-top:.4rem}
h2{font-size:1.55rem;border-bottom:1px solid var(--line);padding-bottom:.25rem}
h3{font-size:1.25rem}
p{margin:.75rem 0}
ul,ol{padding-left:1.6rem}
li>p{margin:.25rem 0}
li.task{list-style:none;margin-left:-1.25rem}
blockquote{margin:1rem 0;padding:.15rem 1rem;border-left:4px solid var(--line);
color:var(--muted)}
code{font-family:ui-monospace,SFMono-Regular,Consolas,"Liberation Mono",monospace;
font-size:.92em;background:var(--code);padding:.1em .3em;border-radius:.25rem}
pre{background:var(--code);padding:.9rem 1rem;border-radius:.45rem;overflow:auto;
border:1px solid var(--line)}
pre code{background:transparent;padding:0;font-size:.88rem;line-height:1.5}
.table-wrap{overflow-x:auto;margin:1rem 0}
table{border-collapse:collapse;width:100%;font-size:.93rem}
th,td{border:1px solid var(--line);padding:.4rem .55rem;vertical-align:top}
thead th{background:var(--panel)}
hr{border:0;border-top:1px solid var(--line);margin:1.6rem 0}
img{max-width:100%;height:auto}
@media (max-width:820px){.layout{display:block}.sidebar{position:static;max-height:none;
border-right:0;border-bottom:1px solid var(--line);padding-right:0;margin-bottom:1rem}}
""".strip()

SCRIPT = """
(function(){
  var key="ail-docs-theme";
  var saved=null;
  try{saved=localStorage.getItem(key)}catch(e){}
  if(saved){document.documentElement.setAttribute("data-theme",saved)}
  var button=document.getElementById("theme-toggle");
  function current(){
    var attr=document.documentElement.getAttribute("data-theme");
    if(attr){return attr}
    return window.matchMedia&&window.matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light";
  }
  function label(){if(button){button.textContent=current()==="dark"?"Light mode":"Dark mode"}}
  label();
  if(button){button.addEventListener("click",function(){
    var next=current()==="dark"?"light":"dark";
    document.documentElement.setAttribute("data-theme",next);
    try{localStorage.setItem(key,next)}catch(e){}
    label();
  })}
  var input=document.getElementById("search");
  var results=document.getElementById("search-results");
  var root=document.body.getAttribute("data-root")||"";
  var data=null;
  function load(){
    if(data){return Promise.resolve(data)}
    return fetch(root+"search-index.json").then(function(r){
      if(!r.ok){throw new Error("HTTP "+r.status)}
      return r.json();
    }).then(function(value){data=value;return value});
  }
  function clear(){while(results.firstChild){results.removeChild(results.firstChild)}}
  function add(text,href){
    var a=document.createElement("a");
    a.textContent=text;a.href=href;
    results.appendChild(a);
  }
  if(input&&results){
    input.addEventListener("input",function(){
      var query=input.value.trim().toLowerCase();
      clear();
      if(query.length<2){return}
      if(!data){
        add("Loading search index...","#");
      }
      load().then(function(index){
        clear();
        var shown=0;
        index.forEach(function(page){
          if(shown>=12){return}
          var title=page.title||page.path;
          var body=(page.text||"").toLowerCase();
          var match=(title+" "+(page.headings||[]).join(" ")).toLowerCase().indexOf(query);
          if(match<0&&body.indexOf(query)<0){return}
          add(title,root+page.path);
          shown++;
        });
        if(!shown){add("No matches","#")}
      }).catch(function(){
        clear();add("Search needs a web server","#");
      });
    });
  }
})();
""".strip()


class Page:
    def __init__(self, src, html_rel, title):
        self.src = src
        self.html_rel = html_rel
        self.title = title


def _sidebar(entries, current):
    start = posixpath.dirname(current.as_posix()) or "."

    def href(target):
        return escape(posixpath.relpath(target.as_posix(), start), True)

    def link(entry):
        current_attr = ' aria-current="page"' if entry.html_rel == current else ""
        return '<li><a href="%s"%s>%s</a></li>' % (
            href(entry.html_rel), current_attr, escape(entry.title))

    roots = [entry for entry in entries if len(entry.html_rel.parts) == 1]
    groups = {}
    for entry in entries:
        if len(entry.html_rel.parts) > 1:
            groups.setdefault(entry.html_rel.parts[0], []).append(entry)
    parts = ['<a class="brand" href="%s">AIL documentation</a>' % href(Path("index.html")),
             '<input class="search" id="search" type="search" placeholder="Search docs"'
             ' aria-label="Search docs">', '<div id="search-results" aria-live="polite"></div>',
             '<button class="theme" id="theme-toggle" type="button">Dark mode</button>',
             "<nav>", "<ul>"]
    parts.extend(link(entry) for entry in roots)
    for name in sorted(groups):
        parts.append('<li><div class="group-title">%s</div><ul>' % escape(name))
        parts.extend(link(entry) for entry in groups[name])
        parts.append("</ul></li>")
    parts.extend(["</ul>", "</nav>"])
    return "\n".join(parts)


def _page_html(title, sidebar, body, root_prefix):
    return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="generator" content="tools/docs_site.py">
<title>%s - AIL documentation</title>
<style>
%s
</style>
</head>
<body data-root="%s">
<a class="skip" href="#main">Skip to content</a>
<div class="layout">
<aside class="sidebar">
%s
</aside>
<main id="main">
<article>
%s
</article>
</main>
</div>
<script>
%s
</script>
</body>
</html>
""" % (escape(title), CSS, escape(root_prefix, True), sidebar, body, SCRIPT)


def _plain_text(body):
    text = re.sub(r"<[^>]+>", " ", body)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:6000]


def build(docs_root, out_root):
    docs_root = Path(docs_root).resolve()
    out_root = Path(out_root).resolve()
    markdown = sorted(path for path in docs_root.rglob("*.md") if path.is_file())
    entries = []
    for src in markdown:
        rel = src.relative_to(docs_root)
        html_rel = rel.with_suffix(".html")
        title = first_heading(src) or rel.stem.replace("_", " ").title()
        entries.append(Page(src, Path(html_rel.as_posix()), title))
    has_index = any(entry.html_rel == Path("index.html") for entry in entries)
    if not has_index:
        entries.append(Page(None, Path("index.html"), "Index"))
    entries.sort(key=lambda entry: (entry.html_rel != Path("index.html"),
                                    entry.html_rel.as_posix()))
    warnings = []
    code_blocks = [0]
    external = {}
    search = []
    repo_root = docs_root.parent
    if out_root.exists():
        shutil.rmtree(out_root)
    out_root.mkdir(parents=True)
    for entry in entries:
        target = out_root / entry.html_rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if entry.src is None:
            links = "\n".join(
                '<li><a href="%s">%s</a></li>' % (escape(page.html_rel.as_posix(), True),
                                                  escape(page.title))
                for page in entries if page.src is not None)
            body = ("<h1>AIL documentation</h1>\n"
                    "<p>These pages are generated from the Markdown files in "
                    "<code>docs/</code>.</p>\n<ul>\n%s\n</ul>" % links)
            title = entry.title
        else:
            renderer = PageRenderer(entry.src, docs_root, entry.html_rel,
                                    warnings, code_blocks, repo_root, external)
            body = renderer.render(entry.src.read_text(encoding="utf-8", errors="replace"))
            title = entry.title
        start = posixpath.dirname(entry.html_rel.as_posix()) or "."
        root_prefix = posixpath.relpath(".", start)
        if root_prefix == ".":
            root_prefix = ""
        else:
            root_prefix += "/"
        sidebar = _sidebar(entries, entry.html_rel)
        target.write_text(_page_html(title, sidebar, body, root_prefix), encoding="utf-8")
        search.append({
            "title": title,
            "path": entry.html_rel.as_posix(),
            "headings": [heading for _level, heading, _slug in
                         (renderer.headings if entry.src is not None else [])],
            "text": _plain_text(body),
        })
    external_blocks = [0]
    published = set()
    while external:
        rel = next(iter(external))
        kind = external.pop(rel)
        if rel in published:
            continue
        published.add(rel)
        source = repo_root / rel
        if kind == "copy":
            target = out_root / "_repo" / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            continue
        if kind == "dir":
            html_rel = Path("_repo") / rel / "index.html"
            target = out_root / html_rel
            target.parent.mkdir(parents=True, exist_ok=True)
            start = posixpath.dirname(html_rel.as_posix()) or "."
            items = []
            for child in sorted(source.iterdir(), key=lambda path: path.name):
                child_rel = rel / child.name
                if child.is_dir():
                    items.append("<li>%s/</li>" % escape(child.name))
                elif child.suffix.lower() in (".md", ".markdown"):
                    external[child_rel] = "markdown"
                    child_pub = Path("_repo") / child_rel.with_suffix(".html")
                    href = posixpath.relpath(child_pub.as_posix(), start)
                    items.append('<li><a href="%s">%s</a></li>'
                                 % (escape(href, True), escape(child.name)))
                else:
                    items.append("<li>%s</li>" % escape(child.name))
            body = ("<h1>Directory: %s</h1>\n<ul>\n%s\n</ul>"
                    % (escape(rel.as_posix()), "\n".join(items)))
            title = "Directory: %s" % rel.as_posix()
        else:
            html_rel = Path("_repo") / rel.with_suffix(".html")
            target = out_root / html_rel
            target.parent.mkdir(parents=True, exist_ok=True)
            renderer = PageRenderer(source, docs_root, html_rel, warnings,
                                    external_blocks, repo_root, external,
                                    external_mode=True)
            body = renderer.render(source.read_text(encoding="utf-8", errors="replace"))
            title = first_heading(source) or rel.stem.replace("_", " ").title()
        start = posixpath.dirname(html_rel.as_posix()) or "."
        root_prefix = posixpath.relpath(".", start)
        if root_prefix == ".":
            root_prefix = ""
        else:
            root_prefix += "/"
        sidebar = _sidebar(entries, html_rel)
        target.write_text(_page_html(title, sidebar, body, root_prefix), encoding="utf-8")
    for src in sorted(path for path in docs_root.rglob("*") if path.is_file()):
        if src.suffix.lower() in (".md", ".markdown"):
            continue
        rel = src.relative_to(docs_root)
        target = out_root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
    (out_root / "search-index.json").write_text(
        json.dumps(search, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8")
    return entries, warnings, code_blocks[0]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Render docs/ as a static site")
    parser.add_argument("root", nargs="?", default="docs", help="Markdown directory")
    parser.add_argument("-o", "--output", default="site", help="output directory")
    args = parser.parse_args(argv)
    root = Path(args.root)
    if not root.is_dir():
        print("docs_site: %s is not a directory" % root, file=sys.stderr)
        return 2
    entries, warnings, blocks = build(root, Path(args.output))
    for warning in warnings:
        print("unconverted: %s" % warning, file=sys.stderr)
    print("docs_site: rendered %d pages from %d Markdown files with %d fenced code blocks"
          % (len(entries), sum(1 for entry in entries if entry.src is not None), blocks))
    if warnings:
        print("docs_site: %d unconverted construct%s"
              % (len(warnings), "" if len(warnings) == 1 else "s"), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
