from dataclasses import dataclass

@dataclass
class Row:
    a: int
    word: str

print(Row(1, "x"))
print(repr(Row(2, "y")))
