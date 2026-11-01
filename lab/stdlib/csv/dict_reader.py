import csv
import io

text = "id,name,score\n1,Alice,90\n2,Bob,85\n\n3,Carol,95\n"
reader = csv.DictReader(io.StringIO(text))
for row in reader:
    print(row["id"], row["name"], row.get("score"), row.get("missing", "n/a"))
print("fields:", reader.fieldnames)

given = csv.DictReader(io.StringIO("Alice,90\nBob,85\n"), fieldnames=["name", "score"])
for row in given:
    print(row["name"], row["score"])
