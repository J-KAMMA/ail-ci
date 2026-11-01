import csv
import io

fields = ["id", "name", "note"]
buffer = io.StringIO()
writer = csv.DictWriter(buffer, fieldnames=fields, restval="-", extrasaction="ignore")
writer.writeheader()
writer.writerow({"id": 1, "name": "Alice", "note": "hello, world"})
writer.writerow({"id": 2, "name": "Bob"})
writer.writerow({"id": 3, "name": "Carol", "note": "x", "extra": "ignored"})
print(repr(buffer.getvalue()))

text = "id,name,note\n1,Alice,hi\n2,Bob,\n"
reader = csv.DictReader(io.StringIO(text))
for row in reader:
    print(sorted(row.items()))
