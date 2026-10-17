Write a complete Python 3.12 program that solves the task below.

Task: Track accounts; failed withdrawals raise a custom InsufficientFunds exception that is caught and printed as 'error: <acc> needs <missing> more'; balance prints 'acc=balance'. Print final balances too.

Input (read from standard input): Several lines: 'deposit ACC AMOUNT', 'withdraw ACC AMOUNT', 'balance ACC AMOUNT' (the amount is ignored for balance); ACC in acc1, acc2, acc3.

Output: write the result to standard output exactly as described. Print nothing else.

Requirements: standard library only; ordinary readable Python with type hints where natural; define main() and end with
if __name__ == "__main__":
    main()

Reply with the program in a single ```python code block and nothing else.