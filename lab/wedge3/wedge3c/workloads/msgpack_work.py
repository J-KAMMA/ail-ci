"""msgpack workload: pack/unpack nested records.

`MSGPACK_PUREPYTHON=1` selects the pure-Python fallback; without it the C extension is the
native baseline (no Rust rewrite of msgpack exists).  The output is a deterministic digest,
so a byte difference is visible.
"""
import hashlib
import msgpack

RECORDS = 400
ROUNDS = 110


def make_record(i):
    return {
        "id": i,
        "name": "user-%04d" % i,
        "active": (i % 3) == 0,
        "score": (i * 0.125) - 7.5,
        "tags": ["tag%d" % (i % 5), "tag%d" % ((i + 2) % 7), "x" * (i % 9)],
        "nested": {"a": i, "b": [i, i + 1, i + 2], "c": {"z": None, "y": True}},
        "blob": bytes([i % 256, (i * 3) % 256, (i * 7) % 256]),
        "empty": [],
    }


def main():
    records = [make_record(i) for i in range(RECORDS)]
    payload = {"version": 1, "records": records, "tail": [None, False, True, 3.5, "end"]}
    packed = b""
    digest = hashlib.sha256()
    for _ in range(ROUNDS):
        packed = msgpack.packb(payload)
        digest.update(packed)
        back = msgpack.unpackb(packed, raw=False, strict_map_key=False)
        assert back == payload, "round trip changed the value"
    print("records %d rounds %d" % (RECORDS, ROUNDS))
    print("packed bytes %d" % len(packed))
    print("sha256 %s" % digest.hexdigest())
    print("first %r" % (packed[:24],))
    print("last %r" % (packed[-16:],))
    print("tail %r" % (payload["tail"],))


main()
