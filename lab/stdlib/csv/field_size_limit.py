import csv
import io

old = csv.field_size_limit()
print("default limit positive:", old > 0)
csv.field_size_limit(10)
try:
    next(csv.reader(io.StringIO("x" * 50 + "\n")))
except csv.Error as exc:
    print("too long:", exc)
csv.field_size_limit(old)
print(next(csv.reader(io.StringIO("short\n"))))

csv.field_size_limit(100)
rows = list(csv.reader(io.StringIO("a,b\nc,d\n")))
print("rows under the limit:", rows)
print("limit restored:", csv.field_size_limit(old) >= 100)
