import hashlib


def main() -> None:
    blobs = [b"first object", b"second object", b"first object", b"third object", b"second object"]
    store: dict[str, bytes] = {}
    for blob in blobs:
        key = hashlib.sha256(blob).hexdigest()
        if key not in store:
            store[key] = blob
    print("unique", len(store))
    for blob in blobs:
        key = hashlib.sha256(blob).hexdigest()
        print(key, store[key] == blob)
    for key in store:
        print(key[0:12], len(store[key]))


main()
