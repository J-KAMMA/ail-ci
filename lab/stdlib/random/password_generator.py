import random
import string


def main() -> None:
    random.seed(12345)
    letters = list(string.ascii_letters + string.digits)
    symbols = list("!@#$%^&*")
    password = []
    for _ in range(12):
        password.append(random.choice(letters))
    password[3] = random.choice(symbols)
    print("".join(password))
    token = random.choices(letters, k=8)
    print("".join(token))
    random.shuffle(password)
    print("".join(password))


main()
