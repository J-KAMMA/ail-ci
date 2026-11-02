from array import array


def main():
    stock = array('q', [4, 9, 2, 9, 7])
    stock.insert(1, 5)
    stock.insert(-100, 1)
    stock.insert(100, 0)
    print(stock.tolist())
    print(stock.count(9), stock.index(9))
    print(stock.index(9, 3))
    stock.remove(2)
    print(stock.pop(), stock.pop(0))
    print(stock.tolist(), 9 in stock)
    try:
        stock.remove(99)
    except ValueError as exc:
        print("ValueError", exc)
    try:
        stock.index(99)
    except ValueError as exc:
        print("ValueError", exc)
    try:
        stock.pop(50)
    except IndexError as exc:
        print("IndexError", exc)
    print(stock.tolist())


main()
