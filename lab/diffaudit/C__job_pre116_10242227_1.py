# C?-job-pre116-10242227-1: a saved generator whose lazy body can raise.
def helper(a, b):
    return a % b


def main():
    g = (helper(5, 0) for _ in range(1))
    try:
        print(next(g))
    except ZeroDivisionError as e:
        print("caught", e)


main()
