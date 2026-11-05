"""gen_big.py [DIR]: write one ~20 MB input per tool into DIR (default: data).

The seed is fixed so the generated inputs and the recorded timings are repeatable.
"""
import random
import sys
from pathlib import Path

SIZE = 20 * 1024 * 1024
CITIES = ["London", "New York", "Manchester", "Paris", "Tokyo", "Lagos", "Lima", "Oslo"]
NOTES = ["plain", "café crème", "say \"hi\"", "a,b", "ok"]


def write_csvcut(path: Path, rnd: random.Random) -> None:
    with path.open("w", encoding="utf-8") as out:
        out.write("id,name,city,score,note\n")
        i = 0
        while out.tell() < SIZE:
            out.write("%d,user%d,%s,%d,\"%s\"\n" % (
                i, i, CITIES[rnd.randrange(len(CITIES))], rnd.randrange(1000),
                NOTES[rnd.randrange(len(NOTES))]))
            i += 1


def write_uniqc(path: Path, rnd: random.Random) -> None:
    with path.open("w", encoding="utf-8") as out:
        i = 0
        while out.tell() < SIZE:
            line = "line %d %s" % (i, CITIES[rnd.randrange(len(CITIES))])
            for _ in range(1 + rnd.randrange(4)):
                out.write(line + "\n")
            i += 1


def write_tsort(path: Path, rnd: random.Random) -> None:
    names = ["n%06d" % i for i in range(5000)]
    with path.open("w", encoding="utf-8") as out:
        while out.tell() < SIZE:
            a = rnd.randrange(len(names) - 1)
            b = a + 1 + rnd.randrange(min(50, len(names) - a - 1))
            out.write("%s %s\n" % (names[a], names[b]))


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent / "data"
    out.mkdir(parents=True, exist_ok=True)
    rnd = random.Random(20261105)
    write_csvcut(out / "big_csvcut.csv", rnd)
    write_uniqc(out / "big_uniqc.txt", rnd)
    write_tsort(out / "big_tsort.txt", rnd)
    for name in ("big_csvcut.csv", "big_uniqc.txt", "big_tsort.txt"):
        print(name, (out / name).stat().st_size)
    return 0


if __name__ == "__main__":
    sys.exit(main())
