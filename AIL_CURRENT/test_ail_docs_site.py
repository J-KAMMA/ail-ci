"""The docs site: the link checker and the generator agree with docs/.

The checker must find no relative link or anchor break in docs/.  The generator must
render one page per Markdown file (plus index.html), report every fenced code block, and
write a site whose HTML links pass the same checker.  A small synthetic tree proves that
a broken link and an unsupported construct make the tools exit 1 and name file:line.
"""
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
DOCS = REPO / "docs"
LINKS = REPO / "tools" / "docs_links.py"
SITE = REPO / "tools" / "docs_site.py"
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
CLOSE = re.compile(r"^ {0,3}(?:`{3,}|~{3,})\s*$")


def run(*args):
    return subprocess.run([sys.executable] + [str(arg) for arg in args],
                          cwd=str(REPO), capture_output=True, text=True, timeout=180)


def fenced_blocks():
    total = 0
    for path in sorted(DOCS.rglob("*.md")):
        fence = None
        for line in path.read_text(encoding="utf-8").splitlines():
            found = FENCE.match(line)
            if fence is None:
                if found:
                    fence = found.group(1)
                    total += 1
            elif CLOSE.match(line):
                fence = None
    return total


class DocsSiteTests(unittest.TestCase):
    def test_docs_links_are_clean(self):
        done = run(LINKS, DOCS)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertNotIn("broken", done.stderr.lower())

    def test_generator_and_built_site(self):
        markdown = sorted(DOCS.rglob("*.md"))
        expected_pages = len(markdown) + (0 if (DOCS / "index.md").exists() else 1)
        expected_blocks = fenced_blocks()
        with tempfile.TemporaryDirectory(prefix="ail-docs-site-") as tmp:
            out = Path(tmp) / "site"
            done = run(SITE, DOCS, "-o", out)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            self.assertNotIn("unconverted", done.stderr.lower())
            found = re.search(r"rendered (\d+) pages from (\d+) Markdown files with "
                              r"(\d+) fenced code blocks", done.stdout)
            self.assertIsNotNone(found, done.stdout)
            self.assertEqual(int(found.group(1)), expected_pages)
            self.assertEqual(int(found.group(2)), len(markdown))
            self.assertEqual(int(found.group(3)), expected_blocks)
            for source in markdown:
                relative = source.relative_to(DOCS).with_suffix(".html")
                self.assertTrue((out / relative).is_file(), relative)
            self.assertTrue((out / "index.html").is_file())
            index = json.loads((out / "search-index.json").read_text(encoding="utf-8"))
            self.assertEqual(len(index), expected_pages)
            self.assertTrue(any(entry["path"] == "index.html" for entry in index))
            for page in out.rglob("*.html"):
                text = page.read_text(encoding="utf-8")
                self.assertNotRegex(text, r"<script[^>]+src=")
                self.assertNotRegex(text, r"<link[^>]+href=[\"']https?:")
            checked = run(LINKS, out)
            self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
            self.assertIn("0 broken links", checked.stdout)

    def test_links_outside_docs_are_published(self):
        with tempfile.TemporaryDirectory(prefix="ail-docs-outside-") as tmp:
            docs = Path(tmp) / "docs"
            docs.mkdir()
            (docs / "a.md").write_text("[outside](../outside.md)\n", encoding="utf-8")
            (Path(tmp) / "outside.md").write_text("# Outside\n", encoding="utf-8")
            out = Path(tmp) / "site"
            done = run(SITE, docs, "-o", out)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            self.assertNotIn("unconverted", done.stderr.lower())
            html = (out / "a.html").read_text(encoding="utf-8")
            self.assertNotIn('href="../outside.md"', html)
            checked = run(LINKS, out)
            self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
            self.assertIn("0 broken links", checked.stdout)

    def test_broken_link_is_named(self):
        with tempfile.TemporaryDirectory(prefix="ail-docs-broken-") as tmp:
            docs = Path(tmp) / "docs"
            docs.mkdir()
            (docs / "a.md").write_text("[missing](gone.md)\n", encoding="utf-8")
            (docs / "b.md").write_text("[anchor](a.md#nope)\n", encoding="utf-8")
            done = run(LINKS, docs)
            self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
            self.assertIn("a.md:1", done.stderr)
            self.assertIn("gone.md", done.stderr)
            self.assertIn("b.md:1", done.stderr)
            self.assertIn("#nope", done.stderr)

    def test_unconverted_construct_is_named(self):
        with tempfile.TemporaryDirectory(prefix="ail-docs-unconverted-") as tmp:
            docs = Path(tmp) / "docs"
            docs.mkdir()
            (docs / "a.md").write_text("# A\n\nText with [a reference][key].\n\n"
                                       "[key]: https://example.com\n", encoding="utf-8")
            out = Path(tmp) / "site"
            done = run(SITE, docs, "-o", out)
            self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
            self.assertIn("unconverted:", done.stderr)
            self.assertIn("a.md:", done.stderr)


if __name__ == "__main__":
    unittest.main()
