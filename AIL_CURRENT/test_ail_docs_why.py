"""Trace every number on docs/WHY.md to a committed result file.

The page is a public claim sheet, so no number in it may be unowned. This test reads
docs/WHY.md and, for every number token on a line, takes the `[source: <repo path>](<link>)`
mark on that same line and checks that the same string occurs in that file. A token with no
mark fails, and so does a token that its marked file does not contain. Every link must
resolve to a file in the repository.

A number token is a run that starts with a digit and may carry thousands commas, a decimal
point, a dash range, a fraction and a trailing x/×/% (for example 3.1x, 6/10, 0.34, 34–102,
116/160). Markdown link targets are removed before scanning, so a path is never counted.

The page must also stay at or under 120 lines, cite at least 12 numbers, and cite at least
4 numbers under "Where it is not there yet".
"""
import re
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PAGE = REPO / "docs" / "WHY.md"
MAX_LINES = 120
MIN_TRACED = 12
LOSS_HEADING = "## Where it is not there yet"
STOP_HEADING = "## Numbers I do not use"

SOURCE = re.compile(r"\[source:\s*(?P<repo>[^\]]+?)\s*\]\((?P<link>[^)]+)\)")
LINK = re.compile(r"(?<!!)\[[^\]]*\]\((?P<link>[^)]+)\)")
NUMBER = re.compile(
    r"(?<![\w.])("
    r"\d[\d,]*(?:\.\d+)?"
    r"(?:[–-]\d[\d,]*(?:\.\d+)?)*"
    r"(?:/\d+)?"
    r"(?:[x×%])?"
    r")(?![\w])"
)


def tracked_files():
    out = subprocess.run(
        ["git", "-C", str(REPO), "ls-files"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return set(out.splitlines())


def visible_text(line):
    line = SOURCE.sub("", line)
    return re.sub(r"\]\([^)]+\)", "]", line)


def read_page():
    return PAGE.read_text(encoding="utf-8").splitlines()


class WhyPage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lines = read_page()
        cls.tracked = tracked_files()

    def test_every_number_is_traced(self):
        failures = []
        traced = set()
        for number, line in enumerate(self.lines, 1):
            tokens = NUMBER.findall(visible_text(line))
            if not tokens:
                continue
            marks = SOURCE.findall(line)
            if not marks:
                failures.append(f"line {number}: number(s) {tokens} with no source mark: {line!r}")
                continue
            texts = []
            for repo_path, _link in marks:
                path = REPO / repo_path.strip()
                if not path.is_file():
                    failures.append(f"line {number}: source file {repo_path!r} does not exist")
                    continue
                texts.append(path.read_text(encoding="utf-8"))
            for token in tokens:
                if any(token in text for text in texts):
                    traced.add(token)
                else:
                    failures.append(
                        f"line {number}: {token!r} is not in {[m[0] for m in marks]}"
                    )
        self.assertFalse(failures, "\n".join(failures))
        self.assertGreaterEqual(
            len(traced), MIN_TRACED, f"only {len(traced)} traced numbers: {sorted(traced)}"
        )

    def test_losses_are_traced(self):
        start = next((i for i, line in enumerate(self.lines) if line.strip() == LOSS_HEADING), None)
        self.assertIsNotNone(start, f"missing heading {LOSS_HEADING!r}")
        end = next(
            (i for i, line in enumerate(self.lines[start + 1:], start + 1)
             if line.strip() == STOP_HEADING),
            len(self.lines),
        )
        tracked = set()
        for line in self.lines[start:end]:
            for token in NUMBER.findall(visible_text(line)):
                tracked.add(token)
        self.assertGreaterEqual(
            len(tracked), 4, f"only {len(tracked)} loss numbers: {sorted(tracked)}"
        )

    def test_links_resolve(self):
        failures = []
        for number, line in enumerate(self.lines, 1):
            for match in LINK.finditer(line):
                target = match.group("link").strip()
                if target.startswith(("http://", "https://", "mailto:", "#")):
                    continue
                resolved = (PAGE.parent / target).resolve()
                if not resolved.is_file():
                    failures.append(f"line {number}: link {target!r} does not resolve")
                elif not str(resolved.relative_to(REPO)) in self.tracked:
                    failures.append(f"line {number}: link {target!r} is not a committed file")
        self.assertFalse(failures, "\n".join(failures))

    def test_every_source_is_committed(self):
        failures = []
        for number, line in enumerate(self.lines, 1):
            for repo_path, _link in SOURCE.findall(line):
                name = repo_path.strip()
                if not (REPO / name).is_file():
                    failures.append(f"line {number}: missing source {name!r}")
                elif name not in self.tracked:
                    failures.append(f"line {number}: source {name!r} is not committed")
        self.assertFalse(failures, "\n".join(failures))

    def test_page_length(self):
        self.assertLessEqual(len(self.lines), MAX_LINES)


if __name__ == "__main__":
    unittest.main()
