import decimal
import tomllib

DOC = '''
pi = 3.14159
scientific = 6.626e-34
whole = 5.0
negative = -0.5
inf = inf
'''


def main():
    data = tomllib.loads(DOC, parse_float=decimal.Decimal)
    print("parser", "Decimal")
    for key in data:
        value = data[key]
        print(key, type(value).__name__, value)
    print("sum", data["pi"] + data["negative"])
    print("is decimal", type(data["pi"]).__name__ == "Decimal")


main()
