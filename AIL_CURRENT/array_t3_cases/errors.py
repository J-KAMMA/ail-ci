import math
import ail_array as ta


def attempt(n: int):
    a = ta.array([1.0, 2.0, 3.0], ta.f32)
    b = ta.array([1.0, 2.0, 3.0, 4.0], ta.f32)
    d = ta.array([1.0, 2.0, 3.0], ta.f64)
    i = ta.array([1, 2, 3], ta.int32)
    e = ta.zeros(0, ta.f32)
    if n == 0:
        print(a + b)
    elif n == 1:
        print(a + d)
    elif n == 2:
        print(d * a)
    elif n == 3:
        print(a - i)
    elif n == 4:
        print(ta.dot(a, b))
    elif n == 5:
        print(ta.dot(a, d))
    elif n == 6:
        print(ta.minimum(a, d))
    elif n == 7:
        print(a[3])
    elif n == 8:
        print(a[-4])
    elif n == 9:
        a[5] = 1.0
    elif n == 10:
        print(ta.min(e))
    elif n == 11:
        print(ta.argmax(e))
    elif n == 12:
        print(ta.frombytes(bytes([1, 2, 3, 4, 5]), ta.f32))
    elif n == 13:
        print(ta.zeros(-2, ta.f32))
    elif n == 14:
        a += b
    elif n == 15:
        a[0:2] = b
    elif n == 16:
        print(ta.sum(d, acc=ta.f32))
    elif n == 17:
        print(ta.dot(d, d, acc=ta.f32))
    elif n == 18:
        print(ta.maximum(a, b))
    elif n == 19:
        print(a == d, a != d, a == b, a == a.copy())
    elif n == 20:
        print(a / 0.0, e + 1.0, ta.sum(e), ta.dot(e, e))
    elif n == 21:
        print(a[1.5])
    elif n == 22:
        a[0:2] = d[0:2]


def main():
    for n in range(23):
        try:
            attempt(n)
        except IndexError as e:
            print(n, "IndexError", e)
        except ValueError as e:
            print(n, "ValueError", e)
        except TypeError as e:
            print(n, "TypeError", e)
    q = ta.array([1.0, 2.0, 3.0], ta.f32)
    try:
        q += ta.array([1.0, math.nan], ta.f32)
    except ValueError as e:
        print("ValueError", e)
    print(q)


main()
