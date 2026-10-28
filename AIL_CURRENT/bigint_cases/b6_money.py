class Money:
    def __init__(self, c: int):
        self.c = c
    def __str__(self) -> str:
        return "%d.%02d" % (self.c // 100, self.c % 100)
def main():
    print(Money(12345))
    print(Money(5))
    print(Money(-195))
main()
