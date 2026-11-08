a = 1
b = 2
c = 1
g = 1
h = 2
step = 0


def bump():
    global a
    a = 50
    return 8


def bump2():
    global c
    c = 70
    return 9


def key():
    global step
    step = step * 10 + 1
    return 'k'


def val():
    global step
    step = step * 10 + 2
    return 3


def bump3(n):
    global g
    g = 100
    return n + 1


def main():
    d = {}
    d[0] = [a, b, bump()]
    print(d)

    # Two positions, the later one a call.
    e = {}
    e[0] = [c, bump2()]
    print(e)

    # The key is evaluated before the list display.
    f = {}
    f[key()] = [val(), 4]
    print(step, f['k'][0])

    # A non-simple element between two plain reads keeps left-to-right order.
    k = {}
    k[0] = [g, bump3(h), g]
    print(k)


main()
