# C?-job-pre138-10250109-2: integer % by zero inside a fused closure.
def make():
    return lambda a, b: a % b

f = make()
try:
    print(f(5, 0))
except ZeroDivisionError:
    print("caught")
