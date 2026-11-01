import csv
import os

path = "csv_file_roundtrip.tmp"
rows = [
    ["id", "value"],
    ["1", "alpha"],
    ["2", "beta,gamma"],
    ["3", "line\nbreak"],
]
handle = open(path, "w", newline="")
writer = csv.writer(handle)
writer.writerows(rows)
handle.close()

handle = open(path, newline="")
reader = csv.reader(handle)
for row in reader:
    print(reader.line_num, row)
handle.close()
os.remove(path)
