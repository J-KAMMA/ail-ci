# stdtop-datekey-1: date / datetime / time as a dict key
from datetime import date, datetime, time

a = date(2024, 1, 15)
b = date(2024, 1, 16)
d = {a: 10, b: 20}
d[a] += 5
print(d.get(a), d[b])
print(a in d, date(2024, 1, 17) in d)
print(sum(d.values()))
t1 = time(1, 2)
t2 = time(1, 3)
s = {t1, t2, t1}
print(len(s), t1 in s)
m = datetime(2024, 1, 15, 3, 4)
print(m in {m: 0})
print(a == date(2024, 1, 15), a != b)
