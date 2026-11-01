import copy

def main() -> None:
    source = {"name": "demo", "items": [1, 2], "meta": {"ok": True}}
    shallow = copy.copy(source)
    shallow["name"] = "changed"
    shallow["items"].append(3)
    del shallow["meta"]
    print(source)
    print(shallow)
    deep = copy.deepcopy(source)
    deep["items"].append(4)
    deep["meta"]["ok"] = False
    print(source)
    print(deep)
    empty = {}
    print(copy.copy(empty), copy.deepcopy(empty))

main()
