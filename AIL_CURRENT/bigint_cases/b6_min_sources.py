class Box:
    def __init__(self, v: int):
        self.v = v

def via_arg(x: int) -> int:
    return x + 1

def via_item(xs: list[int]) -> int:
    return xs[0] + 1

def via_attr(b: Box) -> int:
    return b.v + 1

def main():
    x = -9223372036854775807 - 1
    print(via_arg(x))
    print(via_item([x]))
    print(via_attr(Box(x)))
main()
