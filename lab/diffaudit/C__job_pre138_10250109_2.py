# C?-job-pre138-10250109-2: integer % by zero in a fused closure.
# A single expression is compiled as the fused pipeline (pymod in pyfront.py); the
# equivalent Python is `try: sum(1 % x for x in [1, 0]) except ZeroDivisionError: ...`.
sum(1 % x for x in xs)
