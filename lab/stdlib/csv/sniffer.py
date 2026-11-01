import csv

sample = "name;age;city\nAlice;30;Paris\nBob;25;Rome\n"
sniffer = csv.Sniffer()
dialect = sniffer.sniff(sample)
print(dialect.delimiter)
for row in csv.reader(sample.splitlines(True), dialect):
    print(row)

print("header:", sniffer.has_header(sample))
for candidate in ["a|b\n1|2\n", "a\tb\n1\t2\n"]:
    print("delimiter:", sniffer.sniff(candidate).delimiter)

quoted = 'a,b\n"x,y",2\n'
print("quoted delimiter:", sniffer.sniff(quoted).delimiter)
print("quotechar:", sniffer.sniff(quoted).quotechar)
