"""Write a large Markdown corpus for the mdlite benchmark.

Usage: python3 make_big.py [OUT] [MEGABYTES]

OUT defaults to big.md inside a fresh temporary directory; the path that was
written is printed.  MEGABYTES defaults to 20.  The content is assembled from a
fixed pool of blocks with a fixed random seed, so two runs produce the same
bytes on the same Python version.
"""

import os
import random
import sys
import tempfile


SEED = 20260101
MEGABYTES = 20


TOPICS = (
    "compiler", "parser", "runtime", "standard library", "benchmark",
    "documentation", "test suite", "packaging", "review", "release",
)


def heading(rng, number):
    level = rng.randrange(1, 7)
    topic = TOPICS[rng.randrange(len(TOPICS))]
    return "#" * level + " " + topic.capitalize() + " notes " + str(number) + "\n"


def paragraph(rng):
    topic = TOPICS[rng.randrange(len(TOPICS))]
    return (
        "The *" + topic + "* pass is described as **important** and the "
        "`" + topic + "_check` helper returns a [report](https://example.org/"
        + topic + ") when it finishes. Values 1 < 2 & 3 > 0 and \"quotes\" stay escaped.\n"
    )


def bullets(rng):
    lines = ["- first " + TOPICS[rng.randrange(len(TOPICS))] + " item",
             "- second item with *style* and `code`"]
    if rng.randrange(2):
        lines.append("  - nested item one")
        lines.append("  - nested item two")
    lines.append("- third item")
    return "\n".join(lines) + "\n"


def ordered(rng):
    count = rng.randrange(2, 6)
    lines = []
    for index in range(count):
        lines.append(str(index + 1) + ". ordered step " + str(index + 1))
    return "\n".join(lines) + "\n"


def quote(rng):
    topic = TOPICS[rng.randrange(len(TOPICS))]
    return (
        "> A quoted remark about the " + topic + ".\n"
        "> It continues on a second line with **strength**.\n"
    )


def fence(rng):
    language = ("python", "sh", "text", "html")[rng.randrange(4)]
    return (
        "```" + language + "\n"
        "value = " + str(rng.randrange(1000)) + "\n"
        "name = \"" + TOPICS[rng.randrange(len(TOPICS))] + "\"\n"
        "```\n"
    )


def rule(rng):
    return "---\n\nA plain paragraph after a rule, number " + str(rng.randrange(1000)) + ".\n"


def unicode_block(rng):
    return "Non-ASCII: こんにちは世界 and café and ✨ " + str(rng.randrange(100)) + ".\n"


BUILDERS = (paragraph, bullets, ordered, quote, fence, rule, unicode_block)


def make_document(megabytes):
    """Return the corpus text, at least `megabytes` MiB of UTF-8 bytes."""
    rng = random.Random(SEED)
    target = megabytes * 1024 * 1024
    total = 0
    number = 0
    parts = []
    while total < target:
        number += 1
        parts.append(heading(rng, number))
        parts.append("\n")
        block = BUILDERS[rng.randrange(len(BUILDERS))](rng)
        parts.append(block)
        parts.append("\n")
        total += len(block.encode("utf-8")) + 32
    return "".join(parts)


def main(argv):
    megabytes = MEGABYTES
    if len(argv) > 1:
        out = argv[1]
    else:
        out = os.path.join(tempfile.mkdtemp(prefix="mdlite-big-"), "big.md")
    if len(argv) > 2:
        megabytes = int(argv[2])
    text = make_document(megabytes)
    with open(out, "w", encoding="utf-8") as stream:
        stream.write(text)
    print(out)
    print("bytes:", len(text.encode("utf-8")))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
