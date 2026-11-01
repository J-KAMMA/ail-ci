import cmath


def roots(a: float, b: float, c: float) -> list[complex]:
    disc = complex(b * b - 4.0 * a * c, 0.0)
    root = cmath.sqrt(disc)
    return [(-b + root) / (2.0 * a), (-b - root) / (2.0 * a)]


def main() -> None:
    cases: list[complex] = [complex(1.0, 0.0), complex(1.0, -1.0), complex(2.0, 0.0)]
    labels: list[str] = ["two real", "double", "two complex"]
    index = 0
    while index < len(cases):
        label = labels[index]
        if label == "two real":
            answer = roots(1.0, -3.0, 2.0)
        elif label == "double":
            answer = roots(1.0, 2.0, 1.0)
        else:
            answer = roots(1.0, 0.0, 4.0)
        print(label, repr(answer[0]), repr(answer[1]))
        index = index + 1
    try:
        print(roots(0.0, 1.0, 2.0))
    except ZeroDivisionError as exc:
        print("zero leading coefficient:", exc)
    print("sum of roots", repr(roots(1.0, -5.0, 6.0)[0] + roots(1.0, -5.0, 6.0)[1]))
    print("product of roots", repr(roots(1.0, -5.0, 6.0)[0] * roots(1.0, -5.0, 6.0)[1]))
    print("real check", cmath.isclose(roots(1.0, -3.0, 2.0)[0], complex(2.0, 0.0)))


main()
