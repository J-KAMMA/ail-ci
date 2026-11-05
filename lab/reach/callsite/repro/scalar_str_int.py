# A str at one site and an int at another (the strparam "call sites disagree" refusal).
def show(v):
    return "<" + str(v) + ">"


print(show("a"))
print(show(42))
