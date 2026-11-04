import hashlib


def main() -> None:
    names = ["md5", "sha1", "sha256", "sha512", "sha3_256", "blake2b", "blake2s"]
    for name in names:
        print(name, hashlib.new(name, b"the quick brown fox").hexdigest())
    try:
        hashlib.new("not-a-hash", b"abc")
    except ValueError as exc:
        print("ValueError:", exc)
    print(hashlib.new("sha-256", b"abc").hexdigest())


main()
