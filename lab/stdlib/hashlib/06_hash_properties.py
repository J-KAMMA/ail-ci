import hashlib


def main() -> None:
    for name in ["md5", "sha1", "sha224", "sha256", "sha384", "sha512"]:
        h = hashlib.new(name)
        print(name, h.name, h.digest_size, h.block_size)
    for name in ["sha3_256", "sha3_512"]:
        h = hashlib.new(name)
        print(name, h.name, h.digest_size, h.block_size)
    for name in ["blake2b", "blake2s"]:
        h = hashlib.new(name)
        print(name, h.name, h.digest_size, h.block_size)


main()
