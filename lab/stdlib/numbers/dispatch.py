import numbers


class Rectangle:
    def __init__(self, width, height):
        self.width = width
        self.height = height


def area(shape):
    if isinstance(shape, Rectangle):
        return shape.width * shape.height
    if isinstance(shape, numbers.Integral):
        return shape * shape
    if isinstance(shape, numbers.Real):
        return shape * shape
    if isinstance(shape, numbers.Complex):
        return shape
    raise TypeError("cannot take the area of %r" % (shape,))


def main():
    for shape in [Rectangle(2, 3), 4, 2.5, True, "x", None]:
        try:
            print(type(shape).__name__, area(shape))
        except TypeError as exc:
            print("TypeError", exc)
    print(area(Rectangle(1.5, 2)))
    box = Rectangle(1, 2)
    print(isinstance(box, (numbers.Number, Rectangle)))


main()
