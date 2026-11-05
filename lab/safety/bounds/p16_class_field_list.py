class Bucket:
    def __init__(self, items: list[int]) -> None:
        self.items = items

    def last(self) -> int:
        return self.items[len(self.items) - 1]


b: Bucket = Bucket([9, 8, 7])
print("last", b.last(), "size", len(b.items))
print("all", b.items)
print("past", b.items[len(b.items)])
