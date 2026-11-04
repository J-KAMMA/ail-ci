import hashlib
import hmac


def main() -> None:
    key = b"shared secret"
    message = b"transfer 10 units to example.org"
    tag = hmac.new(key, message, "sha256")
    print("tag", tag.hexdigest())
    print("name", tag.name, "size", tag.digest_size, "block", tag.block_size)
    print("equal", hmac.compare_digest(tag.digest(), hmac.new(key, message, "sha256").digest()))
    print("different", hmac.compare_digest(tag.digest(), hmac.new(key, message + b"!", "sha256").digest()))
    print("text", hmac.compare_digest("same", "same"), hmac.compare_digest("same", "other"))
    print("sha3", hmac.new(key, message, hashlib.sha3_256).hexdigest())


main()
