import marshal

strings = ["", "a", "hello", "hello_world", "hello world", "caf\xe9"]
for s in strings:
    raw = marshal.dumps(s, 2)
    back = marshal.loads(raw)
    print("str", back == s, len(back), raw.hex())

byte_vals = [b"", b"abc", b"\x00\xff\x7f", b"marshal-bytes"]
for b in byte_vals:
    raw = marshal.dumps(b, 2)
    back = marshal.loads(raw)
    print("bytes", back == b, len(back), raw.hex())
