# C?-job-pre165-10250411-1: nested def called before its def statement
def outer():
    try:
        return inner()
    except Exception as exc:
        return type(exc).__name__ + ": " + str(exc)
    def inner():
        return 42

print(outer())

def outer2(flag):
    def f():
        return 1
    if flag:
        f = lambda: 2
    return f()

print(outer2(True))

def outer3():
    def f():
        return 7
    return f()

print(outer3())

def outer4(n):
    try:
        return g(n)
    except Exception as exc:
        return type(exc).__name__
    for g in (lambda v: v + 1,):
        pass

print(outer4(3))
