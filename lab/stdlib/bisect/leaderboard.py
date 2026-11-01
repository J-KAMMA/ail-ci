import bisect


def add_score(board, score):
    bisect.insort(board, score)


def rank_range(board, score):
    low = bisect.bisect_left(board, score)
    high = bisect.bisect_right(board, score)
    return low, high


def main():
    board = []
    for score in [50, 90, 70, 90, 30, 70, 70]:
        add_score(board, score)
    print("board", board)
    for score in [30, 70, 90, 100]:
        low, high = rank_range(board, score)
        print(score, "count", high - low, "better", len(board) - high, "rank", low + 1)
    low = bisect.bisect_left(board, 70)
    high = bisect.bisect_right(board, 70)
    print("middle", board[low:high])
    print("bounds", bisect.bisect_left(board, 70, 2), bisect.bisect_right(board, 70, lo=2, hi=6))


main()
