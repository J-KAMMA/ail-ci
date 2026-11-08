import marshal

values = [
    2**31,
    -(2**31) - 1,
    2**62,
    -(2**62),
    2**70,
    -(2**70),
]
for x in values:
    raw = marshal.dumps(x, 2)
    back = marshal.loads(raw)
    print(type(back).__name__, back == x, back, raw.hex())
