import marshal

values = [
    0.0,
    -0.0,
    1.5,
    -3.25,
    0.125,
    3.141592653589793,
    1e100,
    -1e100,
]
for x in values:
    raw = marshal.dumps(x, 2)
    back = marshal.loads(raw)
    print(type(back).__name__, back == x, raw.hex())
