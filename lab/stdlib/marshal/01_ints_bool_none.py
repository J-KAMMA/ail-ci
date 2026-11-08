import marshal

values = [
    None,
    True,
    False,
    0,
    1,
    -1,
    42,
    -42,
    2147483647,
    -2147483648,
    2**40,
    -(2**40),
    9223372036854775807,
    -9223372036854775807 - 1,
]
for x in values:
    raw = marshal.dumps(x, 2)
    back = marshal.loads(raw)
    print(type(back).__name__, back == x, raw.hex())
