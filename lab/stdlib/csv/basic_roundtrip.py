import csv
import io

rows = [
    ["name", "city"],
    ["Alice", "New York"],
    ["Bob", "San Francisco"],
]
buffer = io.StringIO()
writer = csv.writer(buffer)
writer.writerow(rows[0])
writer.writerows(rows[1:])
text = buffer.getvalue()
print(repr(text))

reader = csv.reader(io.StringIO(text))
for row in reader:
    print(row)
