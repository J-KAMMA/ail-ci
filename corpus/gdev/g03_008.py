# task: Approximate the integral of sin(x) from 0 to pi with the trapezoidal rule using 1000 subintervals and print the error against the exact value 2.
import math


def trapezoidal(f, a: float, b: float, n: int) -> float:
    """Approximate the integral of f over [a, b] using n trapezoidal subintervals."""
    h = (b - a) / n
    total = 0.5 * (f(a) + f(b))
    for i in range(1, n):
        total += f(a + i * h)
    return total * h


def main() -> None:
    a = 0.0
    b = math.pi
    n = 1000
    exact = 2.0

    approx = trapezoidal(math.sin, a, b, n)
    error = approx - exact

    print(f"Approximation (trapezoidal, n={n}): {approx:.10f}")
    print(f"Exact value: {exact:.10f}")
    print(f"Error (approx - exact): {error:.10e}")
    print(f"Absolute error: {abs(error):.10e}")


if __name__ == "__main__":
    main()
