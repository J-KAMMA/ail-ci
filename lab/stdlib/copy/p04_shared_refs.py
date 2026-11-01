import copy

def main() -> None:
    shared = [1, 2]
    source = [shared, shared, {"same": shared}]
    result = copy.deepcopy(source)
    print(result[0] is result[1])
    print(result[0] is result[2]["same"])
    print(result[0] is shared)
    result[0].append(3)
    print(shared)
    print(result[1])
    print(result[2]["same"])
    result[2]["same"].append(4)
    print(result[0])

main()
