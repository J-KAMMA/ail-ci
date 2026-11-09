import hashlib
import msgpack

values = [None, True, False, 0, -1, 2 ** 63 - 1, -2 ** 63, 3.5, "", "x" * 40,
          b"", b"\x00\xff", [], {}, {"a": [1, 2, {"b": None}]}, list(range(10)),
          {"s": "abc", "l": [True, False, None], "n": {"x": 1}}]
for v in values:
    packed = msgpack.packb(v, use_bin_type=True)
    print(hashlib.sha256(packed).hexdigest(), len(packed), repr(msgpack.unpackb(packed, raw=False)))
class Box:
    pass


box = Box()
box.value = {"a": [1, 2, {"b": None}]}
packed = msgpack.packb(box.value, use_bin_type=True)
print("attr", hashlib.sha256(packed).hexdigest(), len(packed), repr(msgpack.unpackb(packed, raw=False)))
