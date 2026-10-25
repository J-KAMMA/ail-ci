x = 2**70
print(list(range(x, x+3)), len(range(x, x+3)))
print(range(2**70)[2**69])
r = range(x, x+10, 3)
print(list(r), len(r), x+3 in r, x+4 in r)
for i in range(x, x+2):
    print(i)
print(range(x)[-1])
print(list(range(-x, -x+2)))
print(list(range(0, x, x//2)))
try:
    print(len(range(0, x, 3)))
except OverflowError as e:
    print('OE', e)
print(list(reversed(range(x, x+3))))
