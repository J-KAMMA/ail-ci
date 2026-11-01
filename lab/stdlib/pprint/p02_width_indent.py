import pprint

items = {
    "alpha": [1, 2, 3, 4, 5],
    "beta": {"x": "long string value here", "y": [10, 20]},
}

for width in (20, 40, 80):
    print("width", width)
    print(pprint.pformat(items, width=width, indent=2))

print("indent 3")
pprint.pprint(items, indent=3, width=35)
print("indent 0")
print(pprint.pformat(items, indent=0, width=30))
