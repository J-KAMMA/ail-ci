import copy
from copy import copy as clone, deepcopy as deep_clone

def main() -> None:
    pair = ([1], 2)
    shallow = clone(pair)
    deep = deep_clone(pair)
    print(shallow is pair)
    print(shallow[0] is pair[0])
    print(deep is pair)
    print(deep[0] is pair[0])
    deep[0].append(3)
    print(pair)
    print(deep)

    frozen = frozenset({1, 2})
    print(clone(frozen) is frozen)
    print(deep_clone(frozen) is frozen)
    print(sorted(deep_clone(frozen)))

    numbers = {1, 2}
    a = copy.copy(numbers)
    b = copy.deepcopy(numbers)
    a.add(3)
    b.add(4)
    print(sorted(numbers))
    print(sorted(a))
    print(sorted(b))
    print(numbers is a, numbers is b)

main()
