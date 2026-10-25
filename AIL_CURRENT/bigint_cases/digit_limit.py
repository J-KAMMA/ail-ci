try:
    int('1'*5000)
except ValueError as e:
    print(e)
try:
    int('1'*4301)
except ValueError as e:
    print(e)
print(len(str(int('1'*4300))))
try:
    int('1'*4301, 10)
except ValueError as e:
    print(e)
try:
    int('x'*5000)
except ValueError as e:
    print(str(e)[:50])
