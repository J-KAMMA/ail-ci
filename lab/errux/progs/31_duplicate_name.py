# line: 9
# names: duplicate AIL name
class C:
    x = 1

class D(C):
    pass

class C:
    pass
print("ok")
