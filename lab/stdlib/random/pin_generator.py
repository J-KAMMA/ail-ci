import random


def main() -> None:
    random.seed(424242)
    for index in range(5):
        code = random.getrandbits(20)
        print("token", index, code, "%06d" % (code % 1000000))
    pin = random.randrange(1000, 10000)
    print("pin", pin)
    print("bits", random.getrandbits(16))
    print("short", random.getrandbits(0))


main()
