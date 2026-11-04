import hashlib


def main() -> None:
    for name in ["md5", "sha1", "sha224", "sha256", "sha384", "sha512"]:
        print(name, hashlib.new(name, b"").hexdigest())
    for name in ["sha3_224", "sha3_256", "sha3_384", "sha3_512"]:
        print(name, hashlib.new(name, b"").hexdigest())
    print("blake2b", hashlib.blake2b(b"").hexdigest())
    print("blake2s", hashlib.blake2s(b"").hexdigest())
    empty = hashlib.sha256()
    empty.update(b"")
    print("updated", empty.hexdigest() == hashlib.new("sha256", b"").hexdigest())


main()
