import operator


def main() -> int:
    inventory = {"apple": 3, "pear": 5}
    operator.setitem(inventory, "plum", 2)
    operator.setitem(inventory, "apple", 4)
    for name in sorted(inventory):
        print(name, inventory[name])
    operator.delitem(inventory, "pear")
    print(len(inventory), inventory.get("pear", -1))
    try:
        operator.delitem(inventory, "kiwi")
    except KeyError as error:
        print("missing", type(error).__name__, error)
    slots = [10, 20, 30]
    operator.setitem(slots, 1, 99)
    operator.setitem(slots, -1, 33)
    print(slots)
    operator.delitem(slots, 0)
    print(slots)
    try:
        operator.delitem(slots, 5)
    except IndexError as error:
        print("range", type(error).__name__)
    grid = {"row": [1, 2]}
    operator.setitem(grid["row"], 0, 7)
    print(grid)
    return 0


main()
