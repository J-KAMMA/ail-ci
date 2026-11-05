"""Write 20 MB benchmark inputs for histo and ini2json.

Usage: python3 gen_big.py [OUTDIR] [MEGABYTES]

OUTDIR defaults to a fresh temporary directory; the paths that were written are
printed.  MEGABYTES defaults to 20.  A fixed seed makes the content identical
between runs of the same Python version.
"""

import os
import random
import sys
import tempfile

SEED = 20260102
MEGABYTES = 20


def write_histo(path, target):
    rng = random.Random(SEED)
    with open(path, "w", encoding="utf-8") as out:
        size = 0
        while size < target:
            value = "%.4f" % (rng.gauss(100.0, 25.0))
            out.write(value + "\n")
            size += len(value) + 1


def write_ini(path, target):
    rng = random.Random(SEED + 1)
    with open(path, "w", encoding="utf-8") as out:
        size = 0
        section = 0
        while size < target:
            out.write("[section%d]\n" % section)
            size += len("[section%d]\n" % section)
            for index in range(40):
                key = "key_%02d" % rng.randrange(100)
                value = "value-%d-%d" % (section, index)
                line = "%s = %s\n" % (key, value)
                out.write(line)
                size += len(line)
            out.write("\n")
            size += 1
            section += 1


def main() -> int:
    outdir = sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(prefix="datacli-big-")
    megabytes = int(sys.argv[2]) if len(sys.argv) > 2 else MEGABYTES
    os.makedirs(outdir, exist_ok=True)
    target = megabytes * 1024 * 1024
    histo_path = os.path.join(outdir, "histo_big.txt")
    ini_path = os.path.join(outdir, "ini_big.ini")
    write_histo(histo_path, target)
    write_ini(ini_path, target)
    print(histo_path)
    print(ini_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
