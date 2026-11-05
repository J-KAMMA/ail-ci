# A method called with int and float (fcspec3).
class Acc:
    def __init__(self):
        self.n = 0

    def bump(self, by):
        self.n += 1
        return by * 2


a = Acc()
print(a.bump(3))
print(a.bump(1.25))
print(a.n)
