
def sq(x: int) -> int:
    return x * x


if __name__ == "__main__":
    acc = 0
    for i in range(0, 10):
        acc += sq(i)
    print(acc)
