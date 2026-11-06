#!/usr/bin/env python3
"""Check relative links and #anchors in a Markdown tree (and, optionally, a built site).

Usage:
    python3 tools/docs_links.py docs
    python3 tools/docs_links.py site            # auto-detects HTML when there are no Markdown files
    python3 tools/docs_links.py --site site

For every Markdown file the checker follows each relative link: the target must exist
(the path is resolved against the file that holds the link) and, when the link names an
anchor, the target must have a heading with that GitHub-style id.  Absolute URLs,
protocol-relative URLs, and links that leave the checked tree are not followed; a
``../lab/results.md`` link in ``docs/`` is still a relative link and *is* checked against
the repository, because it exists on disk.

When the input is a built site (HTML files), the same rules apply to ``href`` and
``src`` attributes.  Links that leave the site root are ignored: they point at repository
files that a static server does not publish.

Exit status is 0 when nothing is broken, 1 when a link or anchor is broken (one
``file:line:`` line per break), and 2 for a usage error.
"""
from __future__ import annotations

import argparse
import html
import os
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
FENCE_RE = re.compile(r"^ {0,3}(?P<fence>`{3,}|~{3,})(?P<info>.*)$")
ATX_RE = re.compile(r"^ {0,3}(?P<hashes>#{1,6})(?:[ \t]+(?P<text>.*?))?[ \t]*$")
SETEXT_RE = re.compile(r"^ {0,3}(?:=+|-+)[ \t]*$")
LIST_RE = re.compile(r"^ {0,3}(?:[-+*]|\d+[.)])[ \t]+")
BLOCKQUOTE_RE = re.compile(r"^ {0,3}>")
HR_RE = re.compile(r"^ {0,3}(?:(?:\*[ \t]*){3,}|(?:-[ \t]*){3,}|(?:_[ \t]*){3,})$")
LINK_START_RE = re.compile(r"!?\[([^\]]*)\]\(")
ESCAPE_RE = re.compile(r"\\([\\`*{}\[\]()#+\-.!_>~|])")
CODE_RE = re.compile(r"(`+)(.+?)\1")
COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
HTML_ID_RE = re.compile(r"<[A-Za-z][^>]*\bid\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s>]+))")
HREF_RE = re.compile(r"<(?P<tag>a|img)\b[^>]*?\b(?P<attr>href|src)\s*=\s*"
                     r"(?:\"(?P<double>[^\"]*)\"|'(?P<single>[^']*)'|(?P<bare>[^\s>]+))",
                     re.I)


def _plain_inline(text):
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = CODE_RE.sub(r"\2", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[*_~]", "", text)
    return ESCAPE_RE.sub(r"\1", text)


def slugify(text):
    """The id GitHub gives a heading (without the duplicate suffix)."""
    value = _plain_inline(text).strip().lower()
    value = re.sub(r"[^\w\s-]", "", value, flags=re.UNICODE)
    value = re.sub(r"\s", "-", value)
    return value


def _strip_inline_code(line):
    return CODE_RE.sub("", line)


def _strip_comments(line, state):
    """Remove HTML comments from one line; state['open'] tracks a multi-line comment."""
    if state["open"]:
        end = line.find("-->")
        if end < 0:
            return ""
        line = line[end + 3:]
        state["open"] = False
    while "<!--" in line:
        start = line.find("<!--")
        end = line.find("-->", start + 4)
        if end < 0:
            line = line[:start]
            state["open"] = True
            break
        line = line[:start] + line[end + 3:]
    return line


def heading_texts(path):
    """Return heading texts in document order, skipping fenced code and HTML comments."""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    result = []
    fence = None
    comment = {"open": False}
    previous = None
    for raw in lines:
        if fence is not None:
            char, length = fence
            if re.match(r"^ {0,3}%s{%d,}[ \t]*$" % (re.escape(char), length), raw):
                fence = None
            continue
        found = FENCE_RE.match(raw)
        if found:
            marks = found.group("fence")
            fence = (marks[0], len(marks))
            previous = None
            continue
        line = _strip_comments(raw, comment)
        if not line.strip():
            previous = None
            continue
        found = ATX_RE.match(line)
        if found:
            result.append(found.group("text") or "")
            previous = None
            continue
        if previous is not None and SETEXT_RE.match(line):
            result.append(previous)
            previous = None
            continue
        stripped = line.strip()
        if (BLOCKQUOTE_RE.match(line) or LIST_RE.match(line) or HR_RE.match(line)
                or stripped.startswith("|") or stripped.startswith("<!--")):
            previous = None
        else:
            previous = stripped
    return result


def anchors_for(path):
    seen = set()
    counts = {}
    result = set()
    for text in heading_texts(path):
        base = slugify(text)
        if not base:
            continue
        slug = base
        if slug in seen:
            number = counts.get(base, 1)
            while slug in seen:
                number += 1
                slug = "%s-%d" % (base, number)
            counts[base] = number
        seen.add(slug)
        result.add(slug)
    return result


def _destination(line, start):
    """Parse a link destination beginning at ``line[start]``; return (target, end index)."""
    index = start
    while index < len(line) and line[index] in " \t":
        index += 1
    if index < len(line) and line[index] == "<":
        end = line.find(">", index + 1)
        if end < 0:
            return None, len(line)
        target = line[index + 1:end]
        index = end + 1
        while index < len(line) and line[index] in " \t":
            index += 1
        return target, index
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


def iter_links(path):
    """Yield (line number, target) for Markdown links, images and titles."""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    fence = None
    comment = {"open": False}
    for number, raw in enumerate(lines, 1):
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
        line = _strip_inline_code(_strip_comments(raw, comment))
        position = 0
        while True:
            match = LINK_START_RE.search(line, position)
            if not match:
                break
            target, end = _destination(line, match.end())
            if target is not None:
                yield number, target
            position = max(end + 1, match.end())


def _split_target(target):
    path_part = target
    fragment = ""
    if "#" in path_part:
        path_part, fragment = path_part.split("#", 1)
    query = ""
    if "?" in path_part:
        path_part, query = path_part.split("?", 1)
    return path_part, query, fragment


def _display(path, root):
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        try:
            return str(path.relative_to(root.parent))
        except ValueError:
            return str(path)


def check_markdown(root):
    root = Path(root).resolve()
    files = sorted(p for p in root.rglob("*.md") if p.is_file())
    anchor_cache = {}
    breaks = []
    for path in files:
        for number, target in iter_links(path):
            if not target or target.startswith("//") or SCHEME_RE.match(target):
                continue
            path_part, _query, fragment = _split_target(target)
            path_part = unquote(path_part)
            fragment = unquote(fragment)
            if path_part.startswith("/"):
                continue
            if path_part:
                target_path = Path(os.path.normpath(str(path.parent / path_part)))
            else:
                target_path = path
            if not target_path.exists():
                breaks.append("%s:%d: broken link %r: target %s does not exist"
                              % (_display(path, root), number, target,
                                 _display(target_path, root)))
                continue
            if not fragment:
                continue
            suffix = target_path.suffix.lower()
            if suffix in (".md", ".markdown"):
                anchors = anchor_cache.get(target_path)
                if anchors is None:
                    anchors = anchors_for(target_path)
                    anchor_cache[target_path] = anchors
            elif suffix in (".html", ".htm"):
                anchors = anchor_cache.get(target_path)
                if anchors is None:
                    text = target_path.read_text(encoding="utf-8", errors="replace")
                    anchors = {html.unescape(a or b or c) for a, b, c in HTML_ID_RE.findall(text)}
                    anchor_cache[target_path] = anchors
            else:
                continue
            if fragment not in anchors:
                breaks.append("%s:%d: broken anchor %r in %s"
                              % (_display(path, root), number, target,
                                 _display(target_path, root)))
    return files, breaks


def check_html(root):
    root = Path(root).resolve()
    files = sorted(p for p in root.rglob("*.html") if p.is_file())
    anchor_cache = {}
    breaks = []
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in HREF_RE.finditer(text):
            target = match.group("double") or match.group("single") or match.group("bare") or ""
            target = html.unescape(target)
            if not target or target.startswith("//") or SCHEME_RE.match(target):
                continue
            path_part, _query, fragment = _split_target(target)
            path_part = unquote(path_part)
            fragment = unquote(fragment)
            if path_part.startswith("/"):
                continue
            target_path = (path.parent / path_part).resolve() if path_part else path
            try:
                target_path.relative_to(root)
            except ValueError:
                continue
            line = text.count("\n", 0, match.start()) + 1
            if not target_path.exists():
                breaks.append("%s:%d: broken link %r: target does not exist"
                              % (_display(path, root), line, target))
                continue
            if not fragment or target_path.suffix.lower() not in (".html", ".htm"):
                continue
            anchors = anchor_cache.get(target_path)
            if anchors is None:
                body = target_path.read_text(encoding="utf-8", errors="replace")
                anchors = {html.unescape(a or b or c) for a, b, c in HTML_ID_RE.findall(body)}
                anchor_cache[target_path] = anchors
            if fragment not in anchors:
                breaks.append("%s:%d: broken anchor %r in %s"
                              % (_display(path, root), line, target,
                                 _display(target_path, root)))
    return files, breaks


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("root", nargs="?", default="docs",
                        help="Markdown tree to check, or a built site (default: docs)")
    parser.add_argument("--site", action="store_true",
                        help="treat ROOT as built HTML even if it also has Markdown files")
    args = parser.parse_args(argv)
    root = Path(args.root)
    if not root.is_dir():
        print("docs_links: %s is not a directory" % root, file=sys.stderr)
        return 2
    markdown = sorted(root.rglob("*.md"))
    built = sorted(root.rglob("*.html"))
    if args.site or (not markdown and built):
        files, breaks = check_html(root)
        kind = "HTML"
    else:
        files, breaks = check_markdown(root)
        kind = "Markdown"
    for line in breaks:
        print(line, file=sys.stderr)
    if breaks:
        print("docs_links: %d broken link%s in %d %s file%s"
              % (len(breaks), "" if len(breaks) == 1 else "s",
                 len(files), kind, "" if len(files) == 1 else "s"),
              file=sys.stderr)
        return 1
    print("docs_links: %d %s file%s, 0 broken links"
          % (len(files), kind, "" if len(files) == 1 else "s"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
