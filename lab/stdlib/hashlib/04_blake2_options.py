import hashlib


def main() -> None:
    message = b"BLAKE2 options exercise the digest size, key and person fields"
    wide = hashlib.blake2b(message, digest_size=20, key=b"secret-key", person=b"mail-signing")
    print(wide.name, wide.digest_size, wide.block_size, wide.hexdigest())
    narrow = hashlib.blake2s(message, digest_size=16, key=b"key", person=b"person")
    print(narrow.name, narrow.digest_size, narrow.block_size, narrow.hexdigest())
    plain = hashlib.blake2b(message)
    print(plain.name, plain.digest_size, plain.block_size, plain.hexdigest())
    salted = hashlib.blake2b(b"abc", salt=b"0123456789abcdef", person=b"ABCDEFGHIJKLMNOP")
    print(salted.hexdigest())


main()
