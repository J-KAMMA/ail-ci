# bool is not int for printing: f(True) prints True, f(1) prints 1.
def same(x):
    return x


print(same(True))
print(same(1))
print(same(False), same(0))
