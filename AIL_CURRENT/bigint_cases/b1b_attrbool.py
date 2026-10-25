class P:
    def __init__(self, v):
        self.v = v

    def sq(self):
        return self.v * self.v


q = P(("a" == "a") + ("a" == "a"))
for c in "abcdef":
    q.v = q.sq()
print(q.v)
