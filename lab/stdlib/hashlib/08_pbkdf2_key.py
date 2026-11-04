import hashlib


def main() -> None:
    secret = b"correct horse battery staple"
    salt = b"example.org/user/42"
    derived = hashlib.pbkdf2_hmac("sha256", secret, salt, 10000, dklen=32)
    print(len(derived), derived.hex())
    short = hashlib.pbkdf2_hmac("sha256", secret, salt, 1000)
    print(len(short), short.hex())
    long = hashlib.pbkdf2_hmac("sha512", secret, salt, 2048, dklen=64)
    print(len(long), long.hex())
    print(hashlib.pbkdf2_hmac("sha1", secret, salt, 4096, 20).hex())


main()
