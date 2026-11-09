# A broadcast between arrays of different dtypes raises the reference's TypeError at run time (job aicore1).
import ail_array as ta


def main():
    a = ta.zeros((3, 4), ta.f64)
    xr = ta.zeros(4, ta.f32)
    xs = ta.zeros((3, 4), ta.f32)
    col = ta.zeros((3, 1), ta.f64)
    for n in range(3):
        try:
            if n == 0:
                print(a + xr)
            elif n == 1:
                print(xr / a)
            else:
                print(xs * col)
        except TypeError as e:
            print(n, "TypeError", e)


main()
