# C?-job-pre109-10242222-1: negative shift count on typed and mixed paths
def shift(x, n):
    try:
        print(x << n)
    except Exception as exc:
        print(type(exc).__name__, str(exc))

def rshift(x, n):
    try:
        print(x >> n)
    except Exception as exc:
        print(type(exc).__name__, str(exc))

for x in [1, 8]:
    for n in [2, -1]:
        shift(x, n)
        rshift(x, n)
try:
    y = 3
    y <<= -1
    print(y)
except Exception as exc:
    print(type(exc).__name__, str(exc))
try:
    z = 8
    z >>= -2
    print(z)
except Exception as exc:
    print(type(exc).__name__, str(exc))
