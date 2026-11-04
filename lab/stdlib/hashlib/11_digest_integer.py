import hashlib


def main() -> None:
    digest = hashlib.sha256(b"abc").digest()
    value = int.from_bytes(digest[:8], "big")
    print(value)
    print(value > 9007199254740992)
    print(value > 9223372036854775807)
    little = int.from_bytes(digest[:8], "little")
    print(little)
    print(little != value)
    print(value.to_bytes(8, "big").hex() == digest[:8].hex())


main()
