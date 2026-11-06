# task: Use collections.deque as a sliding window to print the maximum of every window of size 3 over a hardcoded list of integers.
from collections import deque


def sliding_window_maximum(nums: list[int], k: int) -> list[int]:
    """Return the maximum of each contiguous window of size k using a monotonic deque."""
    if k <= 0 or not nums:
        return []

    result: list[int] = []
    window: deque[int] = deque()  # stores indices; values are decreasing from front to back

    for i, value in enumerate(nums):
        # Drop indices that have left the current window.
        while window and window[0] <= i - k:
            window.popleft()

        # Remove smaller values from the back; they can never be a window maximum.
        while window and nums[window[-1]] <= value:
            window.pop()

        window.append(i)

        # The front of the deque is the index of the current window's maximum.
        if i >= k - 1:
            result.append(nums[window[0]])

    return result


def main() -> None:
    data: list[int] = [1, 3, -1, -3, 5, 3, 6, 7, 2, 8, 4, 0]
    window_size: int = 3

    maxima = sliding_window_maximum(data, window_size)
    for start, maximum in enumerate(maxima):
        window = data[start:start + window_size]
        print(f"Window {window} -> max {maximum}")


if __name__ == "__main__":
    main()
