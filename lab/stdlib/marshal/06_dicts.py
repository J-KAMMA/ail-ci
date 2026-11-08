import marshal

dicts = [
    {},
    {"a": 1, "b": 2},
    {1: "one", 2: "two"},
    {"nums": [1, 2, 3], "info": ("ok", True, None)},
]
for d in dicts:
    raw = marshal.dumps(d)
    back = marshal.loads(raw)
    print("dict", back == d, len(back), raw.hex())
