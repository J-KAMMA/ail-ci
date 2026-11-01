import csv

sample = "name;age;city\nAlice;30;Paris\nBob;25;Rome\n"
dialect = csv.Sniffer().sniff(sample)
print(dialect.delimiter)
for row in csv.reader(sample.splitlines(True), dialect):
    print(row)
