# task: Compute the Gaussian blur of a fixed 7x7 integer image with a 3x3 kernel using pure Python and print the result rounded to two decimals.
from typing import Final


KERNEL: Final[list[list[int]]] = [
    [1, 2, 1],
    [2, 4, 2],
    [1, 2, 1],
]


def make_image() -> list[list[int]]:
    """Return a fixed, deterministic 7x7 integer image."""
    return [
        [(r * 13 + c * 29 + r * c * 5) % 256 for c in range(7)]
        for r in range(7)
    ]


def gaussian_blur_valid(
    image: list[list[int]],
    kernel: list[list[int]],
) -> list[list[float]]:
    """Apply the kernel in 'valid' mode (no padding), normalized by its sum."""
    kh = len(kernel)
    kw = len(kernel[0])
    scale = sum(sum(row) for row in kernel)

    out_h = len(image) - kh + 1
    out_w = len(image[0]) - kw + 1

    result: list[list[float]] = []
    for i in range(out_h):
        out_row: list[float] = []
        for j in range(out_w):
            acc = 0
            for di in range(kh):
                for dj in range(kw):
                    acc += image[i + di][j + dj] * kernel[di][dj]
            out_row.append(acc / scale)
        result.append(out_row)
    return result


def main() -> None:
    image = make_image()
    blurred = gaussian_blur_valid(image, KERNEL)
    for row in blurred:
        print(" ".join(f"{value:8.2f}" for value in row))


if __name__ == "__main__":
    main()
