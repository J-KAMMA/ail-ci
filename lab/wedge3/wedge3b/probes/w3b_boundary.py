def add1(n: int) -> int:
    return n + 1

def mul(n: int) -> int:
    return n * n

def isbig(n: int) -> bool:
    return n > 10

def half(x: float) -> float:
    return x / 2

def join(a: str, b: str) -> str:
    return a + b

def total(xs: list[int]) -> int:
    s = 0
    for x in xs:
        s += x
    return s

def first(xs: list[int]) -> int:
    return xs[0]

def push(xs: list[int]) -> int:
    xs.append(9)
    return len(xs)

def divide(a: int, b: int) -> int:
    return a // b

def echo(x: int) -> int:
    return x

class Box:
    val = 7

BIG = int('1180591620717411303424')
HUGE = int('1267650600228229401496703205376')
print('add', add1(5), add1(BIG), add1(-1))
print('mul', mul(2**40), mul(-2**40), mul(0))
print('bool', isbig(20), isbig(-1), isbig(HUGE))
print('float', half(3.0), half(-0.0), half(float('inf')), half(float('nan')))
print('str', join('a', 'b'), join('héllo 東京', '!'), join('', ''))
print('list', total([1, 2, 3]), total([]), total([2**62, 2**62]), total([True, 2]))
print('first', first([True]), first([BIG]), first([7]))
xs = [1, 2]
print('mut', push(xs), xs)
for a, b in ((7, 2), (7, 0), (-7, 2)):
    try:
        print('div', divide(a, b))
    except Exception as e:
        print('div-exc', type(e).__name__, e)
box = Box()
d = {'k': 5}
lst = [box.val, d['k']]
print('chan', echo(box.val), echo(d['k']), echo(lst[0]), echo(lst[1]))
print('dflt', add1(0), mul(1))
