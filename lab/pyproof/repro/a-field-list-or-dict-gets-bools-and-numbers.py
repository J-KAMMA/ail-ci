class Box:
    def __init__(self):
        self.v = [0]


b = Box()
b.v[0] = True
print(b.v)
