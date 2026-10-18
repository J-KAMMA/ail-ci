import sys


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        return
    nums = [int(x) for x in data]

    best_len = 1
    best_start = 0
    best_val = nums[0]
    runs = 1 if nums else 0

    cur_len = 1
    cur_start = 0
    for i in range(1, len(nums)):
        if nums[i] == nums[i - 1]:
            cur_len += 1
        else:
            runs += 1
            cur_start = i
            cur_len = 1
        if cur_len > best_len:
            best_len = cur_len
            best_start = cur_start
            best_val = nums[i]

    print(best_len, best_start, best_val, runs)


if __name__ == "__main__":
    main()
