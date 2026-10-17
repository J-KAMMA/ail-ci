Write a complete Python 3.12 program that solves the task below.

Task: Define a dataclass Employee(name, dept, salary, age) with order=True, field defaults and __post_init__ validation; read the CSV into Employee objects, print sorted by default dataclass ordering, the first 5.

Input (read from standard input): CSV text with a header line 'name,dept,salary,age' followed by data rows (names repeat).

Output: write the result to standard output exactly as described. Print nothing else.

Requirements: standard library only; ordinary readable Python with type hints where natural; define main() and end with
if __name__ == "__main__":
    main()

Reply with the program in a single ```python code block and nothing else.