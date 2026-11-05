# Same parameter kinds would give the same return kind only by accident: here the int instance
# returns int and the float instance returns float, which today's clone rule (_clone_return_kind
# must equal the generic return) never builds.
def scale(x, k):
    return x * k


total = 0
for i in range(5):
    total += scale(i, 3)
print(total)
print(scale(0.5, 3))
