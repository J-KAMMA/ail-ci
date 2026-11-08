import marshal

lists = [[], [1, 2, 3], ["x", "y"], [[1, 2], ["a", True]]]
for lst in lists:
    raw = marshal.dumps(lst, 2)
    back = marshal.loads(raw)
    print("list", back == lst, back, raw.hex())

tuples = [(), (1, "hello", False), ((1, 2), (3, 4))]
for tup in tuples:
    raw = marshal.dumps(tup, 2)
    back = marshal.loads(raw)
    print("tuple", back == tup, back, raw.hex())
