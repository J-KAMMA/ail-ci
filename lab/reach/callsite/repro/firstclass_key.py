# Used directly with int and float, and also first-class as key= (keeps one generic instance
# or the general path: never an instance per first-class use).
def neg(x):
    return -x


print(neg(3), neg(2.5))
print(sorted([3, 1, 2], key=neg))
