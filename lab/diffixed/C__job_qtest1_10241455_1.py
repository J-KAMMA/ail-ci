# C?-job-qtest1-10241455-1: __index__ instances as str search bounds
class Ix:
    def __init__(self, n):
        self.n = n
    def __index__(self):
        return self.n

s = "abcabc"
print(s.startswith("bc", Ix(1)))
print(s.endswith("bc", Ix(0), Ix(5)))
print(s.find("bc", Ix(1)))
print(s.count("bc", Ix(1)))
print(s.index("bc", Ix(1)))
print(s.startswith("ab", Ix(-2)))
print(s.find("a", Ix(0), Ix(4)))
