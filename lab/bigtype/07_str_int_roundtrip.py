from ail.types import BigInt


text = "1234567890123456789012345678901234567890"
n: BigInt = int(text)
back = str(n)
print(n)
print(back == text)
print(len(text))


def parse(s: str) -> BigInt:
    return int(s)


m: BigInt = parse(text)
print(m == n)
