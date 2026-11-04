import tomllib

DOC = '''
point = { x = 1, y = 2 }
nested = { a = { b = { c = 3 } }, list = [1, 2] }
animals = [ { name = "dog", legs = 4 }, { name = "bird", legs = 2 } ]
dotted = { a.b.c = "deep", a.b.d = "also" }
array_of_inline = [[1, 2], [3, 4], [5, 6]]
'''


def main():
    data = tomllib.loads(DOC)
    print("point", data["point"]["x"], data["point"]["y"])
    print("nested c", data["nested"]["a"]["b"]["c"])
    print("nested list", data["nested"]["list"])
    for animal in data["animals"]:
        print("animal", animal["name"], animal["legs"])
    print("dotted", data["dotted"]["a"]["b"]["c"], data["dotted"]["a"]["b"]["d"])
    print("matrix rows", len(data["array_of_inline"]))
    print("matrix", data["array_of_inline"])


main()
