import pprint

values = [
    None,
    True,
    3,
    -12,
    2.5,
    "text",
    [1, "a"],
    (1,),
    {},
    [],
    {"k": [1, 2]},
]

for value in values:
    print(pprint.saferepr(value), pprint.isreadable(value), pprint.isrecursive(value))


class Hidden:
    def __repr__(self) -> str:
        return "<hidden>"


item = Hidden()
print(pprint.saferepr(item), pprint.isreadable(item), pprint.isrecursive(item))
