"""Census probe: a >1 MiB file read with read_bytes() and scanned forward.

That shape selects the IR window runtime, which maps the file with mmap() and
releases pages with madvise(). run.py creates big.bin (2 MiB) in the work dir.
"""

from ail import read_bytes


def main() -> None:
    data = read_bytes("big.bin")
    total = 0
    for b in data:
        total += b
    print("sum", total)


main()
