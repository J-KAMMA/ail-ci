import ail_array as ta


def attempt(n: int):
    a = ta.zeros((2, 3), ta.f64)
    b = ta.zeros((4, 5), ta.f64)
    v = ta.zeros(3, ta.f64)
    if n == 0:
        print(ta.matmul(a, b))
    elif n == 1:
        print(a + b)
    elif n == 2:
        print(a[2, 0])
    elif n == 3:
        print(a[0, 3])
    elif n == 4:
        print(a[-3, 0])
    elif n == 5:
        print(a[2])
    elif n == 6:
        a[0, -4] = 1.0
    elif n == 7:
        a[5] = v
    elif n == 8:
        a[0] = ta.zeros(4, ta.f64)
    elif n == 9:
        print(ta.zeros((-1, 3), ta.f64))
    elif n == 10:
        print(ta.zeros((3, -2), ta.f64))
    elif n == 11:
        print(ta.array([[1.0, 2.0], [3.0]], ta.f64))
    elif n == 12:
        a -= b
    elif n == 13:
        print(ta.maximum(a, b))
    elif n == 14:
        print(ta.matmul(a, a))
    elif n == 15:
        print(ta.matmul(ta.zeros((0, 3), ta.f64), ta.zeros((4, 0), ta.f64)))
    elif n == 16:
        print(ta.zeros((2, 3), ta.f64).T.T + ta.zeros((3, 2), ta.f64))


def main():
    for n in range(17):
        try:
            attempt(n)
        except IndexError as e:
            print(n, "IndexError", e)
        except ValueError as e:
            print(n, "ValueError", e)
    print(ta.matmul(ta.zeros((0, 0), ta.f64), ta.zeros((0, 0), ta.f64)))


main()
