import copy

def main() -> None:
    table = {
        ("a", 1): [1, 2],
        ("b", 2): {"nested": [3]},
    }
    other = copy.deepcopy(table)
    other[("a", 1)].append(9)
    other[("b", 2)]["nested"].append(4)
    other[("c", 3)] = []
    print(sorted(table))
    print(sorted(other))
    print(table[("a", 1)])
    print(other[("a", 1)])
    print(table[("b", 2)])
    print(other[("b", 2)])
    print(len(table), len(other))

main()
