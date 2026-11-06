from multiprocessing import Pool


def sq(x: int) -> int:
    return x * x


if __name__ == "__main__":
    with Pool(4) as p:
        acc = sum(p.map(sq, range(10)))
    print(acc)
