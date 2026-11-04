# C?-job-pre138-10250109-2: integer % by zero inside a lambda.
# The row's own example: a lambda computing 1 % x raises a catchable ZeroDivisionError.
f = lambda x: 1 % x
try:
    print(f(0))
except ZeroDivisionError:
    print("caught")
