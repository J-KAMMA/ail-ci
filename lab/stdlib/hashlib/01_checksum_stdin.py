import hashlib
import sys


def main() -> None:
    digest = hashlib.sha256()
    chunk = sys.stdin.buffer.read(65536)
    total = 0
    while len(chunk) > 0:
        digest.update(chunk)
        total += len(chunk)
        chunk = sys.stdin.buffer.read(65536)
    print("bytes", total)
    print("sha256", digest.hexdigest())


main()
