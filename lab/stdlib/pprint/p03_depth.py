import pprint

data = {
    "level1": {
        "level2": {
            "level3": [1, 2, 3],
            "other": "value",
        },
        "sibling": [4, 5],
    },
    "top": True,
}

for depth in (1, 2, 3):
    print("depth", depth)
    print(pprint.pformat(data, depth=depth, width=30))

pprint.pprint(data, depth=1)
print(pprint.PrettyPrinter(depth=2).pformat([[[1], [2]], [[3]]]))
