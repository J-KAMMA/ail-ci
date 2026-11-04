"""Write one 50 MB benchmark input per tool.

Usage: python3 make_big.py [OUTDIR]

OUTDIR defaults to a fresh directory under /tmp.  Every file is assembled
from a fixed random seed, so two runs produce the same bytes on the same
Python version.  The paths that were written are printed.
"""

import os
import random
import sys
import tempfile
from pathlib import Path

SEED = 20261104
TARGET = 50 * 1024 * 1024

WORDS = (
    "alpha", "beta", "gamma", "delta", "epsilon", "zeta", "theta", "kappa",
    "lambda", "sigma", "omega", "compiler", "runtime", "parser", "token",
    "value", "record", "report", "example", "system", "input", "output",
)


def fill(path, chunks, target):
    written = 0
    with open(path, "wb") as handle:
        for chunk in chunks:
            handle.write(chunk)
            written += len(chunk)
            if written >= target:
                break


def gen_wc(rng):
    def chunks():
        number = 0
        while True:
            number += 1
            line = "line %d of the benchmark text with a few words\n" % number
            yield line.encode("utf-8")

    return chunks()


def gen_colsum(rng):
    def chunks():
        yield b"name,value\n"
        number = 0
        while True:
            number += 1
            label = ("row%d-" % number) + "x" * 380
            value = rng.randrange(-1000000, 1000000)
            yield ('"%s",%d\n' % (label, value)).encode("utf-8")

    return chunks()


def gen_topwords(rng):
    def chunks():
        while True:
            words = [WORDS[rng.randrange(len(WORDS))] for _ in range(12)]
            yield (" ".join(words) + "\n").encode("utf-8")

    return chunks()


def gen_grepn(rng):
    def chunks():
        number = 0
        while True:
            number += 1
            if number % 500 == 0:
                yield ("record %d carries the needle here\n" % number).encode("utf-8")
            else:
                yield ("record %d is an ordinary line of text\n" % number).encode("utf-8")

    return chunks()


def gen_jsonfield(rng):
    def chunks():
        number = 0
        while True:
            number += 1
            if number % 7 == 0:
                yield ('{"id": %d, "name": "%s"}\n'
                       % (number, WORDS[rng.randrange(len(WORDS))])).encode("utf-8")
            else:
                yield ('{"id": %d, "name": "%s", "value": %d}\n'
                       % (number, WORDS[rng.randrange(len(WORDS))], rng.randrange(1000000))).encode("utf-8")

    return chunks()


def gen_hexdump(rng):
    def chunks():
        while True:
            yield bytes(rng.randrange(256) for _ in range(4096))

    return chunks()


GENERATORS = {
    "wc": ("big.txt", gen_wc),
    "colsum": ("big.csv", gen_colsum),
    "topwords": ("big_words.txt", gen_topwords),
    "grepn": ("big_grepn.txt", gen_grepn),
    "jsonfield": ("big.jsonl", gen_jsonfield),
    "hexdump": ("big.bin", gen_hexdump),
}


def main() -> None:
    if len(sys.argv) > 1:
        outdir = Path(sys.argv[1])
        outdir.mkdir(parents=True, exist_ok=True)
    else:
        outdir = Path(tempfile.mkdtemp(prefix="apps_big_"))
    rng = random.Random(SEED)
    for tool in sorted(GENERATORS):
        name, generator = GENERATORS[tool]
        path = outdir / name
        fill(path, generator(rng), TARGET)
        print("%s %s %d" % (tool, path, os.path.getsize(path)))


main()
