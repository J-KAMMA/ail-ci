import hashlib
import sys


def main() -> None:
    data = sys.stdin.buffer.read()
    print("length", len(data))
    print("md5", hashlib.md5(data).hexdigest())
    print("sha1", hashlib.sha1(data).hexdigest())
    print("sha256", hashlib.sha256(data).hexdigest())
    print("sha512", hashlib.sha512(data).hexdigest())
    print("sha3_256", hashlib.sha3_256(data).hexdigest())


main()
