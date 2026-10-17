"""Task definitions: (category, description of what to compute and print, input generator name).

Input format descriptions live in FORMATS, keyed by generator name. build() turns a task into the
statement text shown to the model.
"""
import inputs_lib

FORMATS = {
    "nums": "The first line holds an integer n. The second line holds n integers separated by spaces (they may be negative).",
    "nums_nocount": "One line of space-separated integers (they may be negative).",
    "pos_nums": "The first line holds n. The second line holds n positive integers separated by spaces.",
    "one_int": "One line with a positive integer n.",
    "small_int": "One line with a small positive integer n.",
    "two_ints": "One line with two positive integers a and b.",
    "words_line": "One line of space-separated lowercase words.",
    "words_line_uni": "One line of space-separated words; some contain non-ASCII letters (accents, CJK, Cyrillic, Greek, emoji).",
    "text_lines": "Several lines of text; words are separated by single spaces, some words end with punctuation (, . ! ;), some lines may be empty, some start with a capital letter.",
    "text_uni": "Several lines of text with single-space separators; some words contain non-ASCII letters (accents, CJK, Cyrillic, Greek, emoji); some end with punctuation; some lines may be empty.",
    "one_word": "One line with one lowercase word.",
    "one_word_uni": "One line with one word that may contain non-ASCII characters (accents, CJK, Cyrillic, Greek, emoji).",
    "strings_n": "The first line holds n. The next n lines each hold one lowercase word.",
    "strings_n_uni": "The first line holds n. The next n lines each hold one word that may contain non-ASCII characters.",
    "palin_strings": "The first line holds n. The next n lines each hold one short string of letters a-d (possibly with an x in the middle).",
    "name_scores": "The first line holds n. The next n lines are 'name score' with a lowercase name and an integer 0..100 (names repeat).",
    "name_score_float": "The first line holds n. The next n lines are 'name value' with a lowercase name and a decimal number with two decimals (names repeat).",
    "csv_table": "CSV text with a header line 'name,dept,salary,age' followed by data rows (names repeat).",
    "grid_se": "The first line holds h and w. Then h lines of w characters: '.' open, '#' wall, 'S' start (top-left), 'E' end (bottom-right).",
    "grid_life": "The first line holds h and w. Then h lines of w characters: '.' dead cell, '#' live cell.",
    "grid_digits": "The first line holds h and w. Then h lines of w digits 1..9.",
    "int_matrix": "The first line holds r and c. Then r lines with c integers each.",
    "square_matrix": "The first line holds n. Then n lines with n integers each.",
    "edges_plain": "The first line holds n (nodes 0..n-1) and m. Then m lines 'a b' describing undirected edges. The graph is connected.",
    "edges_w": "The first line holds n (nodes 0..n-1) and m. Then m lines 'a b w' describing undirected edges with positive integer weight w. The graph is connected.",
    "edges_d": "The first line holds n (nodes 0..n-1) and m. Then m lines 'a b' describing directed edges a->b. Some nodes may be unreachable.",
    "edges_dw": "The first line holds n (nodes 0..n-1) and m. Then m lines 'a b w' describing directed edges a->b with positive integer weight w. Some nodes may be unreachable.",
    "edges_disc": "The first line holds n (nodes 0..n-1) and m. Then m lines 'a b' describing undirected edges. The graph may be disconnected.",
    "dag": "The first line holds n (nodes 0..n-1) and m. Then m lines 'a b' meaning a must come before b. The graph is acyclic.",
    "intervals": "The first line holds n. Then n lines 'start end' with start < end.",
    "knap": "The first line holds n and capacity W. Then n lines 'weight value'.",
    "two_strings": "Two lines, each a string over the letters a, b, c.",
    "coins": "Line 1: the number k of coin kinds. Line 2: the k coin values. Line 3: the target amount.",
    "parens": "The first line holds n. The next n lines each hold a string of bracket characters ()[]{} (possibly empty).",
    "balanced_ish": "The first line holds n. The next n lines each hold a string of bracket characters ()[]{} (possibly empty).",
    "expr_lines": "Several lines, each an arithmetic expression with integers, + - * /, spaces and possibly parentheses.",
    "commands": "Several lines of commands: 'push X', 'pop', 'peek', 'size'.",
    "kv_commands": "Several lines of commands: 'set K V', 'get K', 'del K', 'incr K V', 'count' (keys are single letters, V is an integer).",
    "json_records": "One line containing a JSON array of objects with keys id, name, tags (list of strings), score (float), active (bool), and sometimes meta (an object with level int and note string or null). Strings may contain escaped characters or non-ASCII text.",
    "json_nested": "One line containing arbitrary nested JSON (objects, arrays, numbers, strings, booleans, null).",
    "log_lines": "Lines of the form 'YYYY-MM-DD HH:MM:SS [LEVEL] word word code=NNN' with LEVEL in INFO, WARN, ERROR, DEBUG.",
    "emails_text": "Several lines of free text; some contain an email address like first.last@host.tld and/or a phone number like 555-123-4567.",
    "dates": "Several lines, each a date YYYY-MM-DD (all valid).",
    "times": "Several lines, each a time HH:MM in 24-hour format.",
    "floats": "The first line holds n. The second line holds n decimal numbers separated by spaces.",
    "big_ints": "The first line holds n. The second line holds n positive integers (up to 12 digits).",
    "points": "The first line holds n. Then n lines 'x y' with integer coordinates (duplicates possible).",
    "bank_txns": "Several lines: 'deposit ACC AMOUNT', 'withdraw ACC AMOUNT', 'balance ACC AMOUNT' (the amount is ignored for balance); ACC in acc1, acc2, acc3.",
    "robot": "One line of commands: F (move forward one cell), B (move back one cell), L (turn left 90 degrees), R (turn right 90 degrees). The robot starts at (0,0) facing north (+y).",
    "tokens_mixed": "Several lines, each one arbitrary token (maybe an integer, a float, empty, hex like 0x1f, or garbage, possibly with surrounding spaces).",
    "ints_and_queries": "The first line holds n and q. The second line holds n integers. Then q lines 'l r' (0-based inclusive range).",
    "sorted_nums_target": "The first line holds n. The second line holds n integers in non-decreasing order. The third line holds a target integer.",
    "nums_target": "The first line holds n and a target t. The second line holds n integers.",
    "student_records": "The first line holds n. Then n lines 'name grade age score' where grade is A, B or C.",
    "inventory": "Several lines of commands: 'add ITEM QTY', 'remove ITEM QTY', 'report'.",
    "tasks_deps": "The first line holds n. Then n lines 'name duration dep1 dep2 ...' (dependencies are names of earlier tasks, possibly none).",
    "schedule_queue": "The first line holds n and a quantum q. Then n lines 'name burst' (burst time in time units).",
    "tri_sides": "Several lines, each with three positive integers.",
    "word_pairs": "Several lines, each with two lowercase words.",
    "rle_input": "Several lines, each a non-empty lowercase string with repeated runs.",
    "int_lines_4000": "Several lines, each an integer from 1 to 3999.",
    "bin_strs": "Several lines, each a non-empty binary string (0/1).",
    "hex_lines": "Several lines, each a lowercase hexadecimal number without prefix.",
    "matrix_pow": "The first line holds n. Then n lines with n integers (a square matrix). The last line holds an exponent e.",
    "table_pivot": "Several lines 'region,quarter,amount' (comma separated, amount integer).",
    "cipher_in": "The first line holds a shift k. The remaining lines are text (may include punctuation, possibly non-ASCII letters).",
    "money_lines": "Several lines 'kind amount' where kind is item, tax or fee and amount has two decimals.",
    "distinct_sorted": "One line of distinct positive integers in increasing order.",
    "two_lists": "Two lines, each a list of positive integers separated by spaces (lengths may differ slightly).",
    "pairs_str_int": "Several lines 'word number' with a small possibly negative integer.",
    "seed_params": "One line with two integers: a seed and a count n.",
    "two_words_line": "One line with two lowercase words.",
    "temps": "Several lines 'day temperature' with day in mon..fri and an integer temperature (days repeat).",
    "opt_ints_lines": "Several lines; each is an integer, a non-numeric word, or empty.",
    "tuples_lines": "Several lines 'a,b,word' with digits a and b.",
    "cards": "One line with five cards like 'TS 9H KD 2C AS' (rank in 23456789TJQKA, suit in SHDC).",
    "lines_of_cards": "Several lines, each with five cards like 'TS 9H KD 2C AS' (rank in 23456789TJQKA, suit in SHDC).",
    "tokens_ops": "Several lines of space-separated tokens, each a digit 1-9 or one of + - * (possibly malformed sequences).",
}

TASKS = []


def T(cat, desc, gen):
    assert gen in FORMATS, gen
    assert hasattr(inputs_lib, gen), gen
    TASKS.append((cat, desc, gen))


# ---- parsing / numbers ---------------------------------------------------------------------
c = "numbers"
T(c, "Print the sum, minimum, maximum and the mean (rounded to 2 decimals) of the numbers, one per line.", "nums")
T(c, "Print the second largest distinct value, or 'none' if there is no such value.", "nums")
T(c, "Print the numbers sorted ascending, then sorted descending, each on its own line, space separated.", "nums")
T(c, "Print the median (as a float with one decimal when n is even; otherwise the integer).", "nums")
T(c, "Print the mode (smallest value among the most frequent) and its count.", "nums")
T(c, "Print the length of the longest strictly increasing contiguous run.", "nums")
T(c, "Print the maximum subarray sum (Kadane), and the 0-based start and end indices of one such subarray (first one found).", "nums")
T(c, "Print the prefix sums as one space-separated line, then the total of the even-valued numbers.", "nums")
T(c, "Print how many pairs i<j have equal values.", "nums")
T(c, "Remove duplicates keeping first occurrences; print the result on one line.", "nums")
T(c, "Print the numbers with every negative value replaced by its absolute value, then the count of values that changed.", "nums")
T(c, "Rotate the list right by 3 positions (modulo n) and print it.", "nums")
T(c, "Print the product of all numbers modulo 1000003, and the product of the non-zero ones modulo 1000003.", "nums")
T(c, "Partition into negative, zero and positive numbers; print each group on its own line (sorted ascending, '-' if empty).", "nums")
T(c, "Print the running maximum after each element, space separated.", "nums")
T(c, "Print the number of inversions (pairs i<j with a[i] > a[j]).", "nums")
T(c, "Print the index (0-based) of the first element that is larger than all previous elements and equal to the global maximum, plus the number of times the global maximum appears.", "nums")
T(c, "Print the sum of the k largest values for k=1..min(5,n), one per line.", "nums")
T(c, "Print all pairs of values (a, b) with a<b whose sum is zero, as 'a b' lines in sorted order; print 'none' if there are none.", "nums")
T(c, "Print the values as a histogram: for each distinct value in ascending order print 'value: ' followed by that many '*' characters (counts of occurrences).", "nums")
T(c, "Compute the sum of digits of each non-negative number and print the number whose digit sum is largest (ties: the smaller number); ignore negatives.", "nums")
T(c, "Print the list in 'wave' order: sorted ascending, then alternately take from the smallest and the largest end.", "nums")
T(c, "Compute the product of every number except the one at index i, for each i, without using division by zero; print as one line (use Python big integers).", "pos_nums")
T(c, "Print the greatest common divisor and least common multiple of all the numbers.", "pos_nums")
T(c, "Print the numbers that are prime, in input order, space separated, or 'none'.", "pos_nums")
T(c, "Print the prime factorisation of each number in the form 'n = p1^e1 * p2^e2' one per line.", "pos_nums")
T(c, "Print each number in binary (no prefix), octal and hexadecimal (uppercase) separated by tabs.", "pos_nums")
T(c, "Print the number of set bits of each number, and the XOR of all the numbers.", "pos_nums")
T(c, "Print the count of numbers that are perfect squares, and the largest such number or 'none'.", "pos_nums")
T(c, "Print numbers grouped by their remainder modulo 7: one line per remainder that occurs ('r: a b c').", "pos_nums")
T(c, "Print the two numbers with the smallest absolute difference and that difference.", "pos_nums")
T(c, "Print the mean, population variance and population standard deviation, each rounded to 3 decimals.", "floats")
T(c, "Print the sum of the numbers using ordinary float addition, then math.fsum, with 6 decimals each, and whether they are equal as a Python bool.", "floats")
T(c, "Print each number rounded to the nearest integer using Python's round(), then floored and ceiled, as 'r f c' lines.", "floats")
T(c, "Print the largest and smallest numbers formatted with a width of 10, 2 decimals, and thousands separator (format spec ',.2f').", "floats")
T(c, "Print the numbers sorted by absolute value (stable), formatted with 3 decimals, one line.", "floats")
T(c, "Print the numbers in scientific notation with 3 digits after the decimal point, one per line.", "floats")
T(c, "Normalise the numbers to the range [0,1] (min-max); print each with 4 decimals; if all equal print zeros.", "floats")
T(c, "Print the integer part and fractional part (use math.modf) of each number with 3 decimals.", "floats")
T(c, "Print the sum of two integers a and b, their difference, product, floor division, modulo and a**b only when b<=20 (else 'big').", "two_ints")
T(c, "Print gcd(a,b), lcm(a,b), and whether a and b are coprime.", "two_ints")
T(c, "Print a divided by b as a float with 6 decimals, then divmod(a,b), then pow(a, b, 1000007).", "two_ints")
T(c, "Print the integer square root of a, of b, and whether each is a perfect square.", "two_ints")
T(c, "Print the numbers from min(a,b) to max(a,b) that are divisible by 3 or 5 (at most 30 of them, space separated).", "two_ints")
T(c, "Print n! (full big integer), the number of digits of n!, and the number of trailing zeros.", "small_int")
T(c, "Print the first n Fibonacci numbers on one line, then fib(n*3) as a big integer.", "small_int")
T(c, "Print the n-th row of Pascal's triangle and the sum of its squares.", "small_int")
T(c, "Print the Collatz sequence length (steps to reach 1) for each starting number 1..n, then the starting number with the longest sequence.", "small_int")
T(c, "Print all primes up to 10*n using a sieve, 15 per line.", "small_int")
T(c, "Print the multiplication table of size n x n with columns right-aligned to width 4.", "small_int")
T(c, "Print n in Roman numerals for n, 2n, 3n (skip values above 3999), one per line.", "small_int")
T(c, "Print the number of ways to write n as a sum of positive integers (partitions), and the number of ways using distinct parts.", "small_int")
T(c, "Print the digits of 2**(n*10) summed, and the number of digits.", "small_int")
T(c, "Print n converted to base 2, 3, 5, 16 and 36 using a hand-written conversion (digits 0-9a-z), one per line.", "one_int")
T(c, "Print the divisors of n in ascending order, the count of divisors, and their sum.", "one_int")
T(c, "Print whether n is prime, the next prime after n, and the previous prime before n (or 'none').", "one_int")
T(c, "Print n spelled in English words (e.g. 'one hundred twenty-three') for values up to 5000.", "one_int")
T(c, "Print the digital root of n, the reverse of n, and whether n is a palindrome.", "one_int")
T(c, "Print the Euler totient of n and the number of integers in 1..n coprime to n whose digit sum is even.", "one_int")
T(c, "Print the integer n written in balanced ternary using the symbols '-', '0', '+'.", "one_int")
T(c, "For each of the big integers print its square, its number of digits, and its digit sum; then print the sum of all of them.", "big_ints")
T(c, "Print the integer cube root (floor) of each number using integer arithmetic only (binary search).", "big_ints")
T(c, "Print the product of all numbers and the product mod 998244353.", "big_ints")
T(c, "Print the numbers in comma-grouped format ('{:,}') and in hex with 0x prefix, one per line.", "big_ints")

# ---- string processing -----------------------------------------------------------------------
c = "strings"
T(c, "Count the words (split on whitespace) and print the 5 most frequent words with counts, ties broken alphabetically.", "text_lines")
T(c, "Print each line reversed (character-wise), then the number of lines and the number of empty lines.", "text_lines")
T(c, "Print each line title-cased with str.title(), and then the same line with swapcase().", "text_lines")
T(c, "Capitalise the first letter of each sentence (after '.', '!' or at the start), leaving the rest untouched; print the result.", "text_lines")
T(c, "Strip punctuation (, . ! ;) from all words, lowercase them, and print the sorted list of unique words, one per line.", "text_lines")
T(c, "For each line print its length, the length of its longest word, and the longest word itself ('-' for empty lines).", "text_lines")
T(c, "Word-wrap the whole text (joined by single spaces) to lines of at most 20 characters, never breaking words; print the lines with line numbers.", "text_lines")
T(c, "Print a character frequency table for letters only (case-insensitive), sorted by count descending then letter ascending, as 'x: n'.", "text_lines")
T(c, "Print lines that contain the word 'a' or 'e' as whole words, with their 1-based numbers, as '3: text'.", "text_lines")
T(c, "Left-justify, right-justify and centre each line in a width of 40 using '.' as the fill character, one block per line of input.", "text_lines")
T(c, "Print the number of vowels and consonants (ASCII letters only) in the whole text, plus the number of non-ASCII characters.", "text_uni")
T(c, "Print every line with its length in characters and its length in UTF-8 bytes as 'chars bytes text'.", "text_uni")
T(c, "Sort all distinct words (case-sensitive, by Unicode code point) and print them, one per line, with the code point of their first character in hex.", "text_uni")
T(c, "Print each line upper-cased and lower-cased (Python's str.upper/lower), plus the casefolded version if different from lower.", "text_uni")
T(c, "Print the characters of the first non-empty line one per line as 'U+XXXX char' (uppercase hex, at least 4 digits).", "text_uni")
T(c, "Reverse the order of words in each line (keeping spaces single) and print them; then print the total number of distinct characters in the whole text.", "text_uni")
T(c, "Print the longest word by number of characters (first one on ties) and its length, and the longest by UTF-8 byte length.", "text_uni")
T(c, "For each word in the text count how many are palindromes (case-insensitive); print the palindromes in order of appearance.", "text_uni")
T(c, "Print the unique words sorted by (length, word), formatted as a table with the word left-aligned to width 12 and length right-aligned to width 3.", "text_uni")
T(c, "Check that each line is pure ASCII; print 'ascii' or 'non-ascii' for each, then the encoded bytes (as list of ints) of the first non-ASCII line in UTF-8.", "text_uni")
T(c, "Print whether each of the strings is a palindrome ignoring case: 'yes' or 'no', then the count of palindromes.", "palin_strings")
T(c, "Print the longest palindromic substring of each string (first on ties).", "palin_strings")
T(c, "Print each string run-length encoded (e.g. 'aaab' -> 'a3b1').", "rle_input")
T(c, "Print each string compressed as 'a3b' style (count omitted when 1), and check that decoding returns the original; print 'ok' for each.", "rle_input")
T(c, "For each pair of words print 'anagram' or 'not anagram'.", "word_pairs")
T(c, "For each pair print the length of the longest common prefix and the edit (Levenshtein) distance.", "word_pairs")
T(c, "Group the words by their sorted letters (anagram classes); print groups with more than one member, sorted, one group per line.", "strings_n")
T(c, "Print the words sorted by length then alphabetically, and the longest common prefix of all words.", "strings_n")
T(c, "Print each word with its vowels replaced by '*' and the number of replaced characters.", "strings_n")
T(c, "Print the words that contain all five vowels at least once, or 'none'; and the word with the most distinct letters (first on ties).", "strings_n")
T(c, "Print each word reversed, and whether it equals its reverse; then print the concatenation of all words separated by '-'.", "strings_n_uni")
T(c, "Sort the words with Python's default string ordering and with key=str.casefold; print both orders.", "strings_n_uni")
T(c, "For each word print len(), len of its UTF-8 encoding, and whether str.isalpha() and str.isascii() hold.", "strings_n_uni")
T(c, "Print each word padded to width 10 using centre alignment with '*' and its first and last character.", "strings_n_uni")
T(c, "Apply a Caesar cipher with the shift k to all ASCII letters of the text (preserve case; leave other characters unchanged); print the result, then decrypt it and print 'ok' if equal.", "cipher_in")
T(c, "Run a Vigenere-style shift: use the shift k and the position of each letter in the line (shift k+i for i-th letter, ASCII letters only); print the result lines.", "cipher_in")
T(c, "Count words per line, and print the line number with the most words (first on ties) and the average words per line with 2 decimals.", "text_lines")
T(c, "Print the text with each word truncated to 4 characters and an ellipsis '...' appended when truncated.", "words_line")
T(c, "Print the number of distinct words, the first word that appears twice, and the words that appear exactly once in order.", "words_line")
T(c, "Print the words joined with commas, the same with 'and' before the last one, and the words in a column right-aligned to the longest word.", "words_line")
T(c, "Print each word that is an anagram of an earlier word, with the index of its first partner.", "words_line")
T(c, "Print every word with its letters sorted, then a camelCase and a snake_case version of the whole sequence of words.", "words_line")
T(c, "Print the number of distinct letters across all words, the letters that never appear (a-z) and the most frequent letter (alphabetically smallest on ties).", "words_line")
T(c, "Print the words in a sliding window: for window size 3, each triple joined by '+', one per line; fewer than 3 words prints 'short'.", "words_line")
T(c, "Print the word frequencies of the line as 'word=count' sorted by count desc then word asc, then bigram counts (adjacent word pairs) for the top 3.", "words_line")
T(c, "Print each word with its Pig Latin form (move the leading consonant cluster to the end and add 'ay'; words starting with a vowel get 'way').", "words_line")
T(c, "Read the line and print its chunks of size 7 (character-wise) separated by '|', plus the reversed string.", "words_line")
T(c, "Find the longest substring without repeating characters in the whole line (spaces included); print it and its length.", "words_line")
T(c, "Print the line after removing consecutive duplicate characters, and the length before and after.", "words_line")
T(c, "Print whether each word is a valid identifier (str.isidentifier), a keyword (keyword.iskeyword), or neither.", "words_line")
T(c, "Print each distinct pair of words (w1, w2) with w1<w2 that differ in exactly one position and have the same length (at most 20 pairs, sorted).", "words_line")
T(c, "Zip-compare the first half of the word list against the second half, printing 'a<b', 'a=b' or 'a>b' for each pair.", "words_line")
T(c, "Print the one-line text with its words wrapped using textwrap.fill at width 30, and then with textwrap.shorten at width 40.", "words_line")
T(c, "Check whether the two words are rotations of each other, whether one is a subsequence of the other, and print their common letters sorted.", "two_words_line")
T(c, "Print the interleaving (alternating characters) of the two words, and all characters they share sorted without duplicates.", "two_words_line")

# ---- collections ------------------------------------------------------------------------------
c = "collections"
T(c, "Sum scores per name; print names ordered by total score descending then name ascending as 'name total'.", "name_scores")
T(c, "Per name print count, min, max and average (2 decimals) of the scores, in alphabetical order of names.", "name_scores")
T(c, "Print the name with the best single score (first on ties) and the names that appear exactly once.", "name_scores")
T(c, "Use collections.Counter to count names; print the 3 most common via most_common(3), and the total of the rest.", "name_scores")
T(c, "Use defaultdict(list) to group scores per name; print each name with its scores sorted descending.", "name_scores")
T(c, "Rank the names by average score (descending, ties alphabetical) and print the dense rank, name and average with 1 decimal.", "name_scores")
T(c, "Print a histogram of scores bucketed in tens (0-9, 10-19, ..., 100) using '#' marks, only buckets with content.", "name_scores")
T(c, "Print each distinct name and the position (1-based line numbers) of its occurrences.", "name_scores")
T(c, "Maintain a deque of the last 3 scores seen and print the average of the deque after each entry (2 decimals).", "name_scores")
T(c, "Sum values per name using floats; print totals rounded to 2 decimals sorted by name, and the grand total.", "name_score_float")
T(c, "Print the name with the highest average value, and the median value overall.", "name_score_float")
T(c, "Print the top 3 values (with names) using heapq.nlargest, and the bottom 3 using heapq.nsmallest.", "name_score_float")
T(c, "Round each value to the nearest integer with Python's round() and print the integer sum and the sum of the original values formatted with 2 decimals.", "name_score_float")
T(c, "Treat each stack command: push X, pop (print the popped value or 'empty'), peek (print the top or 'empty'), size (print the size). Print outputs in order.", "commands")
T(c, "Treat the commands as a queue (push enqueues, pop dequeues from the front, peek looks at the front) using collections.deque; print outputs for pop/peek/size, with 'empty' when applicable.", "commands")
T(c, "Treat the commands as a priority queue (heapq): push inserts, pop removes the smallest, peek shows the smallest; print results of pop/peek/size.", "commands")
T(c, "Implement a key-value store: 'set K V' stores, 'get K' prints value or 'nil', 'del K' removes and prints 1 or 0, 'incr K V' adds V to the number at K (missing means 0) and prints the new value, 'count' prints the number of keys.", "kv_commands")
T(c, "Implement an LRU cache of capacity 2 using OrderedDict: 'set K V' inserts or updates, 'get K' prints value or -1 and marks it recently used, 'del K' removes (print nothing), 'incr K V' behaves like set with value V, 'count' prints the current size.", "kv_commands")
T(c, "Implement an undo-able key-value store: after each 'set' or 'del' push a snapshot; 'count' prints the number of keys; 'get' prints the value or 'nil'; 'incr' acts as set; at the end print the final state sorted by key.", "kv_commands")
T(c, "Track a bank: deposit adds, withdraw subtracts only if enough funds (otherwise print 'insufficient'), balance prints the balance. Print the final balances sorted by account.", "bank_txns")
T(c, "Track accounts; failed withdrawals raise a custom InsufficientFunds exception that is caught and printed as 'error: <acc> needs <missing> more'; balance prints 'acc=balance'. Print final balances too.", "bank_txns")
T(c, "Track an inventory: add increases stock, remove decreases stock but not below zero (print 'short by N' if too few), report prints every item with its quantity sorted by item name.", "inventory")
T(c, "Track inventory and print the item with the highest stock after every report command, and the total quantity added overall.", "inventory")
T(c, "Compute the set operations of the two lists: union, intersection, symmetric difference, and elements only in the first, each sorted on its own line.", "two_lists")
T(c, "Print the elements of the first list that are not in the second (order preserved, duplicates preserved), the number of common distinct elements, and the Jaccard index with 4 decimals.", "two_lists")
T(c, "Zip the two lists (stop at the shorter), print pairwise sums and products, and the dot product.", "two_lists")
T(c, "Use itertools.zip_longest with fill value 0 to add the two lists elementwise and print the result.", "two_lists")
T(c, "Merge the two lists into one sorted list using heapq.merge after sorting both, and print the merged list and its length.", "two_lists")
T(c, "Count the frequencies of the numbers in both lists with Counter; print the sum of both Counters (as sorted 'k:v' pairs) and the difference of the first minus the second.", "two_lists")
T(c, "Group consecutive equal numbers using itertools.groupby and print each run as 'value x count'.", "nums_nocount")
T(c, "Find the longest run of equal consecutive numbers and the starting index; also print the number of runs.", "nums_nocount")
T(c, "Bucket the numbers by sign and parity into a dict with keys like 'neg-odd'; print keys sorted with their sorted values.", "nums_nocount")
T(c, "Print each number with its rank in the sorted distinct list (0-based coordinate compression), one line.", "nums_nocount")
T(c, "Print the top-3 distinct maximum values using a set and sorted, and the numbers that appear more than once.", "nums_nocount")
T(c, "Maintain a sliding window of size 4 with a deque and print the max of each full window.", "nums_nocount")
T(c, "Print the pair (min, max) of each prefix and the number of times the maximum changed.", "nums_nocount")
T(c, "Count the numbers with a dict, then print the numbers sorted by (count desc, value asc) as 'value count'.", "nums_nocount")
T(c, "Sort the lines 'word number' by number descending, then word ascending, and print them; then print the words with their total numbers via a dict comprehension sorted by key.", "pairs_str_int")
T(c, "Build a dict mapping word -> list of numbers, drop the entries whose numbers sum to zero, and print the rest sorted.", "pairs_str_int")
T(c, "Parse the rows 'a,b,word' into tuples (int, int, str); print them sorted by (b descending, a ascending, word), and the unique tuples count.", "tuples_lines")
T(c, "Use a set of tuples (a,b) to count distinct pairs, then print the pairs with a==b, and the most common word per a value.", "tuples_lines")
T(c, "Convert the rows to namedtuples (fields a, b, word) and print the sum of a, the max of b and the word with the most occurrences.", "tuples_lines")
T(c, "Convert the rows to a list of dataclass instances and print them sorted by word then a, using the repr of the dataclass.", "tuples_lines")
T(c, "Print the temperature statistics per day: min, max, mean (1 decimal) in the order mon..fri for days that appear.", "temps")
T(c, "Print the days sorted by mean temperature descending, and the longest streak of consecutive input lines with a temperature above the overall mean.", "temps")

# ---- parsing / csv / json / re ---------------------------------------------------------------
c = "parsing"
T(c, "Parse the CSV; print the average salary per department (integer division) sorted by department.", "csv_table")
T(c, "Using the csv module, print the oldest employee per department (ties: first listed) as 'dept: name (age)'.", "csv_table")
T(c, "Print the total salary and the number of employees per department as an aligned table with the headers 'dept', 'count', 'total'.", "csv_table")
T(c, "Sort the rows by (dept, -salary, name) and print them back as CSV including the header.", "csv_table")
T(c, "Print the number of distinct names, and the names whose rows appear in at least two different departments.", "csv_table")
T(c, "Using csv.DictReader build a list of dicts; print the highest-paid person overall and the department with the highest average age (2 decimals).", "csv_table")
T(c, "Bucket employees by age decade (20s, 30s, ...) and print the count and mean salary (rounded to integer) of each bucket.", "csv_table")
T(c, "Print for every department the salary range as 'dept: min-max' and the median salary (average of two middles as float when even).", "csv_table")
T(c, "Compute a pivot table of the amounts: rows regions, columns q1..q4 with 0 for missing, plus row and column totals; print aligned with width 7.", "table_pivot")
T(c, "Print the region with the highest total and the quarter with the highest total, and each region's share of the grand total as a percentage with 1 decimal.", "table_pivot")
T(c, "Parse the money lines into decimal.Decimal values; print item subtotal, tax, fee and total exactly (two decimals) using Decimal arithmetic.", "money_lines")
T(c, "Parse amounts with float and then print the sum using round(x, 2) and using Decimal; print whether they match.", "money_lines")
T(c, "Parse each JSON record; print the names of active records sorted, and the average score of all records (2 decimals).", "json_records")
T(c, "Print the JSON re-serialised with sort_keys=True and indent=2 (ensure_ascii=False).", "json_records")
T(c, "Print the JSON re-serialised compactly (separators ',' and ':') with ensure_ascii=True.", "json_records")
T(c, "Collect all tags across records into a Counter and print the counts as a JSON object with sorted keys.", "json_records")
T(c, "Print records with a 'meta' key flattened as 'id: level=<level> note=<note or ->', one per line, sorted by id.", "json_records")
T(c, "Output a JSON list of {id, name_upper, n_tags} for each record, using json.dumps with default settings.", "json_records")
T(c, "Print the top 2 records by score as JSON lines (one json.dumps per record, keys sorted).", "json_records")
T(c, "Compute the depth of the nested JSON, the number of leaves, and print the sorted distinct leaf types by name (e.g. int, str).", "json_nested")
T(c, "Flatten the JSON into 'path = value' lines where the path uses dots for keys and [i] for indices; values printed with json.dumps.", "json_nested")
T(c, "Print the sum of all numbers (ints and floats) found anywhere in the JSON, counting booleans as not numbers; print with repr.", "json_nested")
T(c, "Round-trip the JSON: parse, dump with sort_keys and compact separators, parse again and print whether equal, followed by the dump.", "json_nested")
T(c, "Print the JSON with all strings upper-cased and all integers incremented by one (booleans untouched), as compact JSON.", "json_nested")
T(c, "For every ERROR line print the time (HH:MM:SS) and the code; then print the count per level sorted by level.", "log_lines")
T(c, "Using the re module, extract date, level and code with named groups and print the codes grouped by level; use sorted order.", "log_lines")
T(c, "Parse timestamps with datetime.strptime; print the earliest and latest entries and the difference in whole days between them.", "log_lines")
T(c, "Count log lines per hour of day (00-23), print only non-zero hours as 'HH: n', and the busiest hour.", "log_lines")
T(c, "Print the number of lines per month using the date, and the first WARN line (or 'none').", "log_lines")
T(c, "Sort the lines by their timestamp and print the first five plus the average code value per level (rounded to 1 decimal).", "log_lines")
T(c, "Find all email addresses with a regular expression; print them lowercased, unique and sorted, and the domains with counts.", "emails_text")
T(c, "Extract phone numbers of the form NNN-NNN-NNNN with re.findall and print them with the line number where they occur.", "emails_text")
T(c, "Mask every email with '***@' + domain and every phone with 'XXX-XXX-' + last four digits using re.sub; print the lines.", "emails_text")
T(c, "Use re.split to split every line on commas, spaces, or periods and print the number of resulting non-empty tokens per line.", "emails_text")
T(c, "Validate every date: leap-year aware day checks via calendar; print 'weekday' name (using datetime.date) for each, and the count of weekend dates.", "dates")
T(c, "Print the dates sorted ascending, the day count between the first and last, and the date 100 days after the earliest one.", "dates")
T(c, "Group the dates by ISO week number (isocalendar) and print week -> count sorted.", "dates")
T(c, "Print each date in the format 'Mon DD, YYYY' (using strftime) and the day of year.", "dates")
T(c, "Convert each time HH:MM to minutes since midnight, print the minutes sorted, and the largest gap between consecutive sorted times (circular, wrapping over midnight).", "times")
T(c, "Print each time in 12-hour notation like '3:05 PM', and count the AM times and PM times.", "times")
T(c, "Parse the lines as integers where possible; print 'int N', 'float X', or 'bad TOKEN' (repr of the token) for each line using try/except; the integers must be parsed with int(), floats with float().", "tokens_mixed")
T(c, "For each token print the result of str.strip().isdigit(), isnumeric() and isdecimal() as three booleans separated by spaces, and print repr of the token.", "tokens_mixed")
T(c, "Sum all lines that parse as ints after strip; count the lines that fail; print both.", "tokens_mixed")
T(c, "Parse every non-empty line with ast.literal_eval; print repr of results or 'invalid' on failure.", "tokens_mixed")
T(c, "Evaluate each arithmetic expression with your own recursive descent parser (supporting + - * / and parentheses, true division); print the value with repr, or 'error' for division by zero.", "expr_lines")
T(c, "Evaluate each expression using a shunting-yard to RPN conversion and a stack, printing the RPN form and the result as a float with 4 decimals.", "expr_lines")
T(c, "Tokenise each expression with a regular expression and print the tokens list (repr) and the count of operators.", "expr_lines")
T(c, "Print for each line the postfix evaluation of tokens treating them as RPN (digits push, operators pop two); print the result or 'error' for malformed sequences.", "tokens_ops")
T(c, "For each line report the maximum depth of the nested brackets or 'unbalanced', and the position of the first mismatch (0-based).", "balanced_ish")
T(c, "For each line print 'valid' or 'invalid' using a stack.", "balanced_ish")
T(c, "For each line print the minimum number of bracket insertions needed to make a string balanced, using only the bracket types present; treat each bracket type independently with counters.", "parens")
T(c, "For each line print the length of the longest valid parentheses substring considering only '(' and ')' characters (ignore other characters).", "parens")
T(c, "Count the occurrences of each bracket kind over all lines and print them as a dict with sorted keys using repr.", "parens")
T(c, "Parse a robot command string; track position and heading; print the final position, heading name and the Manhattan distance from the start.", "robot")
T(c, "Run the robot commands and print every distinct visited cell count, the farthest Euclidean distance reached with 3 decimals, and the final position.", "robot")
T(c, "Run the robot and print the path as a list of tuples (repr) for the first 10 visited positions, then print whether it returns to the origin.", "robot")

# ---- grids -------------------------------------------------------------------------------------
c = "grids"
T(c, "BFS from S to E moving in four directions on open cells; print the shortest path length or -1 if unreachable.", "grid_se")
T(c, "BFS from S to E; print the path as a string of U/D/L/R moves (first found in order U, D, L, R) or 'no path'.", "grid_se")
T(c, "DFS (iterative) from S; print how many cells are reachable (including S) and whether E is reachable.", "grid_se")
T(c, "Count the connected components of open cells ('.', 'S', 'E' are open) with 4-connectivity, and the size of the largest.", "grid_se")
T(c, "Print the grid with the cells reachable from S replaced by '+' (keeping S and E marks), then the count of reachable open cells.", "grid_se")
T(c, "Compute for every open cell the distance from S (BFS) and print the grid with distances modulo 10 as digits ('#' for walls, '.' for unreachable).", "grid_se")
T(c, "Use 8-direction movement and BFS to print the shortest path length from S to E, or -1.", "grid_se")
T(c, "Find the number of distinct shortest paths from S to E (4-directional moves, count paths using BFS DP); print 0 if unreachable.", "grid_se")
T(c, "Count the connected groups of '#' cells using 8-connectivity and print the size of each group sorted descending.", "grid_life")
T(c, "Simulate Conway's Game of Life on the grid (non-wrapping borders) for 5 generations; print the grid after each generation separated by a blank line.", "grid_life")
T(c, "Simulate Game of Life with wrap-around (torus) for 4 generations and print the final grid plus the live-cell count.", "grid_life")
T(c, "Find the largest rectangle consisting only of '#' cells and print its area.", "grid_life")
T(c, "Transpose the grid, then rotate it 90 degrees clockwise; print both results.", "grid_life")
T(c, "Flood fill from the top-left cell: if it is '.', fill its connected '.' region with 'o' and print the grid, otherwise print the grid unchanged.", "grid_life")
T(c, "For each cell print the count of neighbouring '#' cells (8 directions) as a digit grid.", "grid_life")
T(c, "Print the perimeter of all '#' cells (edges adjacent to '.' or outside) and the number of '#' cells.", "grid_life")
T(c, "Find the minimum cost path from the top-left to the bottom-right moving right or down only (sum of digits); print the cost and one such path as a string of R/D.", "grid_digits")
T(c, "Find the minimum cost path with 4-directional movement (Dijkstra, cost of entering a cell is its digit, start cost excluded); print the cost.", "grid_digits")
T(c, "Find the maximum sum path from top-left to bottom-right moving right or down, and the number of different maximum sum paths.", "grid_digits")
T(c, "Print the row sums, column sums and both diagonal sums of the digit grid (the diagonals from the top-left corner and the top-right corner extended as far as possible within the grid).", "grid_digits")
T(c, "Find the 2x2 sub-block with the maximum sum (first on ties by row then column) and print its top-left corner and the sum.", "grid_digits")
T(c, "Print the spiral order traversal of the grid on one line.", "grid_digits")
T(c, "For each cell determine whether it is a local maximum (strictly greater than all 4-neighbours); print the coordinates (row col) in row-major order and the count.", "grid_digits")
T(c, "Compute a 2D prefix sum array and answer: the sum of the whole grid, of the top-left quadrant (rows//2, cols//2), and of the bottom-right quadrant.", "grid_digits")
T(c, "Print the matrix transposed, and the matrix multiplied by its transpose (only if both dimensions allow; it always does) as rows of integers.", "int_matrix")
T(c, "Print the matrix with each row sorted ascending, and the columns' maxima.", "int_matrix")
T(c, "Print the rows sorted lexicographically as lists, the row with the largest sum (first on ties), and the number of zero entries.", "int_matrix")
T(c, "Print the matrix elements in a zigzag diagonal order (anti-diagonals alternating directions) on one line.", "int_matrix")
T(c, "Print the number of rows that are palindromes, and the matrix flipped horizontally and vertically.", "int_matrix")
T(c, "Compute the determinant using Fraction-based Gaussian elimination and print it as a fraction in lowest terms (e.g. 7 or 7/2). If not square print 'not square'.", "int_matrix")
T(c, "Print the trace, the determinant (integers via Laplace expansion for n<=6, otherwise 'skip') and whether the matrix is symmetric.", "square_matrix")
T(c, "Compute the matrix raised to the power e with plain integer arithmetic (matrix exponentiation) and print the result matrix; use big integers.", "matrix_pow")
T(c, "Compute the transitive closure (Floyd-Warshall on the matrix entries > 0 as edges) and print it as a 0/1 matrix.", "square_matrix")
T(c, "Rotate the matrix by 90 degrees three times and print the final result; also print whether the matrix is a Latin square.", "square_matrix")
T(c, "Print the sum of the main diagonal and anti-diagonal without double-counting the centre, and the maximum row sum.", "square_matrix")
T(c, "Print the number of 'saddle points' (minimum in its row and maximum in its column) with their coordinates.", "square_matrix")
T(c, "Print the points sorted by (x, y), the bounding box, and the number of distinct points.", "points")
T(c, "Print the convex hull of the points (Andrew's monotone chain) in counter-clockwise order starting from the lowest-leftmost point, one 'x y' per line.", "points")
T(c, "Print the closest pair of points (brute force) with its squared distance, ties by first found in sorted order of the points; if fewer than two points print 'none'.", "points")
T(c, "Print the centroid with 3 decimals, the point farthest from the centroid, and the area of the bounding box.", "points")
T(c, "Print the points grouped by quadrant (I, II, III, IV, axis) with the counts.", "points")
T(c, "Compute the polygon area (shoelace formula) of the points in input order, as a float with 1 decimal, and the perimeter with 3 decimals.", "points")
T(c, "Count the number of right triangles that can be formed from the points (use all triples when n<=25; otherwise only the first 25 points).", "points")
T(c, "Count lattice points pairs (i<j) lying on a common horizontal, vertical or 45-degree diagonal line, and print the counts for each kind.", "points")
T(c, "For each triangle side triple print its type (equilateral, isosceles, scalene, invalid) and the area by Heron's formula with 3 decimals when valid.", "tri_sides")

# ---- graphs ------------------------------------------------------------------------------------
c = "graphs"
T(c, "Run BFS from node 0 and print the visiting order and the distance to every node.", "edges_plain")
T(c, "Run recursive DFS from node 0 visiting neighbours in ascending order; print the preorder and postorder.", "edges_plain")
T(c, "Compute the diameter (longest shortest path) of the tree/graph using BFS from every node, and print it with the pair of endpoints (smallest pair on ties).", "edges_plain")
T(c, "Print the degree of every node and the nodes with the max degree.", "edges_plain")
T(c, "Detect whether the graph is bipartite and print the 2-colouring or 'not bipartite'.", "edges_plain")
T(c, "Detect whether the graph has a cycle and print one cycle as a list of nodes, or 'acyclic'.", "edges_plain")
T(c, "Find all bridges (edges whose removal disconnects the graph) in sorted order using DFS low-link.", "edges_plain")
T(c, "Find all articulation points using DFS low-link and print them sorted.", "edges_plain")
T(c, "Print the number of triangles in the graph.", "edges_plain")
T(c, "Compute the shortest path counts from node 0 to every node (number of distinct shortest paths).", "edges_plain")
T(c, "Print the adjacency list (sorted neighbours) and the adjacency matrix as 0/1 rows.", "edges_plain")
T(c, "Run Dijkstra from node 0 with heapq; print the distance to every node and the path to the farthest node.", "edges_w")
T(c, "Compute a minimum spanning tree with Kruskal using union-find; print its total weight and edges sorted.", "edges_w")
T(c, "Compute the MST with Prim's algorithm and print the total weight; print the number of different MST edge sets cannot be computed so just print the total.", "edges_w")
T(c, "Run Floyd-Warshall and print the matrix of shortest distances (use 'inf' for unreachable).", "edges_w")
T(c, "Print the second shortest distance (strictly greater than the shortest) from node 0 to the last node, or -1 if none.", "edges_w")
T(c, "Run Bellman-Ford from node 0 and print the distances.", "edges_w")
T(c, "Print the shortest path (as node list) from 0 to n-1 with minimal weight, ties broken by fewer edges then lexicographically smaller list.", "edges_w")
T(c, "Print the eccentricity of each node (max shortest distance with weights) and the graph's radius and centre nodes.", "edges_w")
T(c, "Find the connected components using union-find and print their sizes sorted, plus the component containing node 0 as a sorted list.", "edges_disc")
T(c, "Count the connected components using BFS and print them as sorted lists, ordered by their smallest node.", "edges_disc")
T(c, "Print for each component whether it is a tree (m = n-1) or has cycles.", "edges_disc")
T(c, "Topologically sort the DAG using Kahn's algorithm with a min-heap for smallest-first ordering; print the order.", "dag")
T(c, "Print the longest path length (in edges) in the DAG, and the number of distinct topological orders is not needed; print also the count of source nodes and sink nodes.", "dag")
T(c, "Topologically sort using DFS (visit nodes in ascending order) and print the reverse postorder.", "dag")
T(c, "Print the number of paths from node 0..n-1 sources to sinks: count paths from every source to every sink using DP modulo 1000000007; print the total.", "dag")
T(c, "Print whether the directed graph has a cycle (and if so one cycle), using three-colour DFS.", "edges_d")
T(c, "Compute strongly connected components with Tarjan's or Kosaraju's algorithm; print components sorted by smallest node, each as a sorted list.", "edges_d")
T(c, "Print the set of nodes reachable from node 0 (sorted) and those that can reach node 0 (sorted).", "edges_d")
T(c, "Compute the in-degree and out-degree of each node and print nodes where in != out.", "edges_d")
T(c, "Run Dijkstra from node 0; print 'node: dist' for reachable nodes and 'node: unreachable' otherwise.", "edges_dw")
T(c, "Find the shortest cycle through node 0 (sum of weights) in the directed weighted graph, or 'none'.", "edges_dw")
T(c, "Compute the maximum weight path from node 0 using at most 4 edges (DP over edge count); print the weight or 'none'.", "edges_dw")
T(c, "Compute the minimum number of edges to every node from node 0 (BFS) and the total of the weights along the BFS tree edges.", "edges_dw")
T(c, "Resolve task dependencies: print a valid execution order (alphabetical among ready tasks) and the earliest finish time of each task assuming unlimited parallelism, then the project length.", "tasks_deps")
T(c, "Print the critical path (a longest path of dependent tasks by duration) as task names joined by '->' and its total duration.", "tasks_deps")
T(c, "Simulate round-robin scheduling with the given quantum; print the completion time of every process in the input order and the average turnaround time with 2 decimals.", "schedule_queue")
T(c, "Simulate shortest-job-first scheduling (non-preemptive, all arrive at time 0); print the order, the waiting time of each process and the average waiting time with 2 decimals.", "schedule_queue")

# ---- DP and algorithms ---------------------------------------------------------------------------
c = "dp"
T(c, "Solve 0/1 knapsack: print the maximum total value and the chosen item indices (0-based, ascending).", "knap")
T(c, "Solve the unbounded knapsack and print the max value.", "knap")
T(c, "Print the number of subsets of the items whose total weight is at most the capacity, modulo 1000000007 (items may be considered distinct by index).", "knap")
T(c, "Compute the length of the longest common subsequence of the two strings and print one such subsequence.", "two_strings")
T(c, "Compute the edit distance between the two strings (insert, delete, substitute) and print the number of each operation in one optimal alignment as 'ins del sub'.", "two_strings")
T(c, "Compute the longest common substring of the two strings (first found in the first string) and its length.", "two_strings")
T(c, "Count the number of distinct subsequences of the first string equal to the second string, modulo 1000000007.", "two_strings")
T(c, "Check whether the first string matches the second as a pattern where '?' is not present — instead, print whether the second is a subsequence of the first and the number of positions where the strings differ when aligned from the left.", "two_strings")
T(c, "Print the minimum number of coins needed to make the amount (or -1) and one optimal multiset of coins.", "coins")
T(c, "Print the number of ways (combinations, order ignored) to make the amount with the coins, and the number of ordered ways modulo 1000000007.", "coins")
T(c, "Print the length of the longest increasing subsequence (strict) and one such subsequence, using the O(n log n) bisect method for the length.", "nums_nocount")
T(c, "Print the length of the longest non-decreasing subsequence and the length of the longest bitonic subsequence.", "nums_nocount")
T(c, "Print the maximum sum of a subsequence with no two adjacent elements (house robber), taking the values as given (negative allowed).", "nums_nocount")
T(c, "Print the maximum product subarray value.", "nums_nocount")
T(c, "Partition into two subsets with minimum absolute difference of sums for non-negative numbers only (use absolute values of the inputs); print the difference.", "nums_nocount")
T(c, "Print the number of ways to split the sequence into contiguous non-empty parts whose sums are all non-negative, modulo 1000000007.", "nums_nocount")
T(c, "Use bisect to count how many numbers are less than each of the numbers in a sorted copy; print counts as one line, plus the insertion point of 0.", "nums_nocount")
T(c, "Compute the minimum number of jumps to reach the end where each absolute value |a[i]| is the maximal jump length from i (position clamps nothing); print -1 if unreachable (zero value blocks).", "nums_nocount")
T(c, "Count the number of increasing triples i<j<k with a[i]<a[j]<a[k].", "nums_nocount")
T(c, "Merge overlapping closed intervals and print the merged result as 'a b' lines, then the total covered length.", "intervals")
T(c, "Select the maximum number of non-overlapping intervals (greedy by end time) and print the count and the chosen intervals.", "intervals")
T(c, "Print the maximum number of overlapping intervals at any time (sweep line) and the earliest time that happens.", "intervals")
T(c, "Compute the minimum number of rooms needed using a min-heap of end times, and print the total idle time between intervals when merged.", "intervals")
T(c, "For each query range, print the sum, minimum and maximum of the array in that range.", "ints_and_queries")
T(c, "Answer each query with a prefix sum array and a sparse table for range minimum; print 'sum min' pairs.", "ints_and_queries")
T(c, "Build a Fenwick tree (binary indexed tree) over the array and answer each query as the range sum; then add 1 to every even index and answer the queries again.", "ints_and_queries")
T(c, "Answer each query: the number of distinct values in the range, with a simple set per query.", "ints_and_queries")
T(c, "Binary search for the target; print its first and last index (0-based) or -1 -1, and the count of occurrences, using the bisect module.", "sorted_nums_target")
T(c, "Print the lower bound and upper bound positions of the target (hand-written binary search), and the closest value to the target.", "sorted_nums_target")
T(c, "Print all pairs of indices (i<j) whose values sum to the target t (unsorted array), at most 20 pairs; use a dict.", "nums_target")
T(c, "Print the number of subarrays with sum equal to t, using prefix sums and a dict.", "nums_target")
T(c, "Print the length of the shortest subarray with sum at least t (all values are used as given), or 0 if none.", "nums_target")
T(c, "Find three distinct indices i<j<k with a[i]+a[j]+a[k] == t; print the lexicographically smallest triple or 'none'.", "nums_target")
T(c, "Count the number of subsets (by index) with sum equal to t, for the first up to 18 elements; print the count.", "nums_target")
T(c, "Solve the N-Queens puzzle for n = the integer given; print the number of solutions and the first solution (as column indices of each row) in lexicographic order.", "small_int")
T(c, "Generate all permutations of the integers 1..min(n,6) in lexicographic order and print the count and the last permutation; also print the number of derangements of that size.", "small_int")
T(c, "Print all subsets of {1..min(n,5)} ordered by (size, lexicographic) one per line, using itertools.combinations.", "small_int")
T(c, "Generate all balanced parentheses strings with min(n,6) pairs, sorted, and print the count and the first three.", "small_int")
T(c, "Count the number of binary strings of length n without two consecutive ones and print the count modulo 1000000007 plus the first few strings of length min(n,4).", "small_int")
T(c, "Print Catalan numbers C(0)..C(n) using both the DP recurrence and the closed form with math.comb; verify they agree and print 'ok'.", "small_int")
T(c, "Print the Tower of Hanoi move count and the first 10 moves for min(n,10) discs ('A->C' style).", "small_int")
T(c, "Print the n-th ugly number (factors 2, 3, 5) for n up to 60 using a heap or three pointers, and the first 15 ugly numbers.", "small_int")
T(c, "Generate the Gray code sequence for k = min(n, 5) bits and print each code in binary.", "small_int")
T(c, "Print the number of lattice paths from (0,0) to (n,n) moving right or up, plus the number avoiding the diagonal (staying weakly below it), using big ints.", "small_int")
T(c, "Run a sieve to count primes below n*1000, then list twin prime pairs found below 200.", "small_int")
T(c, "Print the digits of the continued fraction expansion for sqrt(n) (first 8 terms; if n is a perfect square print the integer), integer arithmetic only.", "small_int")
T(c, "Print the n-th Fibonacci number modulo 10**9+7 using fast doubling, and the Pisano period for modulo min(n,50)+1.", "small_int")
T(c, "Compute the longest Collatz chain for starting numbers below n*100 with memoization via a dict, printing the winner and the chain length.", "small_int")
T(c, "Solve the stock profit problem: use the integers (with random sign) as daily prices (absolute values), print the maximum profit with one transaction and with unlimited transactions.", "nums_nocount")
T(c, "Print the median of medians by splitting into chunks of 5 (print the medians list and its median), then the exact median.", "nums_nocount")
T(c, "Implement quicksort and merge sort by hand, verify both equal sorted(), and print the sorted list and 'ok'.", "nums")
T(c, "Implement heap sort by hand and a counting sort for the shifted values; print the sorted list and the number of swaps done by bubble sort.", "nums")
T(c, "Implement selection sort and count comparisons and swaps; print the sorted list, comparisons and swaps.", "nums")
T(c, "Implement insertion sort, count shifts, and print the number of shifts; also print the sorted list with positions of original indices (stable argsort).", "nums")
T(c, "Compute the k-th smallest for k=1,2,n using quickselect and compare with sorting; print results.", "nums")
T(c, "Implement a binary search tree with insertion; print the inorder traversal, the height, and the preorder traversal.", "nums")
T(c, "Implement a min-heap by hand with sift-up/sift-down and print the elements popped in order, then compare with heapq.", "nums")
T(c, "Build a trie from the lowercase words, then print the number of nodes, and all words sharing the prefix equal to the first two letters of the first word, sorted.", "strings_n")
T(c, "Implement a union-find with path compression over the words: unite words with the same first letter and print the number of groups and the sizes.", "strings_n")

# ---- sorting / keys -------------------------------------------------------------------------------
c = "sorting"
T(c, "Sort students by grade ascending, then score descending, then name; print 'name grade age score'.", "student_records")
T(c, "Print students grouped by grade (A, B, C) with the average score per grade (2 decimals) and the youngest student in each (first on ties).", "student_records")
T(c, "Print the students with a score at least equal to the 75th percentile (nearest-rank method), sorted by score descending then name.", "student_records")
T(c, "Use sorted() with a key function that returns a tuple, and operator.itemgetter, to sort by age then name; print the first 5.", "student_records")
T(c, "Print the ranking with competition ranking (1,2,2,4) of the students by score descending, with names alphabetical on ties.", "student_records")
T(c, "Using functools.cmp_to_key, sort students by score descending and then by name ascending; print the results.", "student_records")
T(c, "Compute the z-score (population std, 3 decimals) of each student's score and print students with |z| > 1 sorted by name.", "student_records")
T(c, "Count the students per (grade, age) combination, print combinations sorted, and the combination with the most students.", "student_records")
T(c, "Print the words sorted by length descending, then reverse alphabetical.", "strings_n")
T(c, "Print the words sorted by the number of vowels, then by the word; use sorted with a key lambda returning a tuple.", "strings_n")
T(c, "Print the words sorted case-insensitively, stable, by their last letter.", "strings_n")
T(c, "Sort by key=lambda w: (-len(set(w)), w) and print with index numbers; also print the min and max by the same key.", "strings_n")
T(c, "Print the sorted order of the words with natural ordering of embedded numbers: each word is suffixed by its 1-based index in the list ('word12'); sort these numerically on the index parts descending.", "strings_n")
T(c, "Print list.sort() with reverse=True on stable key length, to demonstrate that equal-length words keep input order; print the result.", "strings_n")
T(c, "Sort numbers by the number of 1 bits in binary (ties by value) and print them.", "pos_nums")
T(c, "Sort numbers by their digit sum then value; print each as 'value(digitsum)'.", "pos_nums")
T(c, "Sort the numbers by the last digit, then by value descending.", "pos_nums")
T(c, "Print the numbers sorted by their string representation (lexicographic) and then largest-number-formation: arrange them to form the largest concatenated number; print that number.", "pos_nums")
T(c, "Sort points by distance from the origin (squared distance integer), ties by x then y; print the first 10.", "points")
T(c, "Sort points by angle around the origin (atan2) with ties by distance; exclude the origin; print the first 10.", "points")
T(c, "Sort the lines of a log by level severity (ERROR > WARN > INFO > DEBUG), then by timestamp; print the first 8 lines.", "log_lines")
T(c, "Print the lines sorted by code descending using the integer after 'code='; ties by original order; first 8 lines.", "log_lines")
T(c, "Sort sentences (lines) by number of words descending then alphabetically (lowercase compare); print lines with word counts.", "text_lines")
T(c, "Sort the rows of the matrix by the sum of their entries (ties by lexicographic order), print rows; also sort the columns by the min entry.", "int_matrix")
T(c, "Print the numbers of the 2-element tuple list sorted using key=lambda t: (t[1], -t[0]) where the tuples are read from CSV lines 'a,b,word' (word ignored).", "tuples_lines")
T(c, "Do a stable multi-key sort in two passes (first by word, then by a descending) and print the result; verify equal to a single-pass tuple key.", "tuples_lines")
T(c, "Sort the dates by weekday (Mon=0) then by day of month, print the first 8 with the weekday abbreviation.", "dates")
T(c, "Sort the times by minute-of-hour, then hour; print them back as HH:MM.", "times")

# ---- simulation / state ------------------------------------------------------------------------------
c = "simulation"
T(c, "Simulate a simple linear congruential generator x = (a*x + 11) % 2**31 with a=1103515245 starting from the seed; print the first n values mod 100.", "seed_params")
T(c, "Use random.Random(seed) from the standard library to produce n random integers in [1, 100] and print them, then the sum of random.Random(seed).sample(range(100), 5).", "seed_params")
T(c, "Shuffle the list range(n) with random.Random(seed).shuffle and print the result, then sort it using a hand-written bubble sort counting swaps.", "seed_params")
T(c, "Simulate n coin flips with random.Random(seed).random() < 0.5 as heads; print the heads count, longest streak, and the proportion with 3 decimals.", "seed_params")
T(c, "Simulate a 1-D random walk of n steps with random.Random(seed).choice([-1, 1]); print the final position, max, and min positions.", "seed_params")
T(c, "Roll two dice n times with random.Random(seed).randint(1,6); print the frequency of each sum 2..12 as a histogram of '#'.", "seed_params")
T(c, "Run a bank-queue simulation: customers arrive every 2 time units and each service takes randint(1,5) time units from random.Random(seed); one teller; print the average wait with 3 decimals for n customers.", "seed_params")
T(c, "Play a deterministic card game: shuffle a 52-card deck with random.Random(seed).shuffle, deal 5 cards, and print the hand sorted by rank, and whether it contains a pair.", "seed_params")
T(c, "Implement Monte-Carlo estimation of pi using random.Random(seed) with n*100 samples; print the estimate with 4 decimals.", "seed_params")
T(c, "Evaluate each poker hand: print its category (high card, pair, two pair, three of a kind, straight, flush, full house, four of a kind, straight flush).", "lines_of_cards")
T(c, "For each hand print the ranks sorted by (count desc, rank value desc) and whether all five cards share a suit.", "lines_of_cards")
T(c, "Compare the hands pairwise in order (hand 1 vs hand 2, hand 3 vs hand 4,...) using category then tie-breaking ranks; print the winner index or 'tie'.", "lines_of_cards")
T(c, "Print the hand's total value in blackjack terms (aces 1 or 11, face cards 10) as the best total not exceeding 21 or the minimum total.", "cards")
T(c, "Simulate the cards: sort the five cards by rank ascending and print them, then print the longest run of consecutive ranks.", "cards")
T(c, "Simulate an elevator that starts at floor 1 and serves the requested floors given by the integers in order (nearest-first among remaining requests); print the order of service and the total distance travelled.", "nums_nocount")
T(c, "Simulate a ball bouncing: each integer is a height; drop from each height h with 0.5 rebound ratio until below 1; print the total distance travelled per drop with 2 decimals (heights taken as absolute values).", "nums_nocount")
T(c, "Simulate a parking lot with the integers as car IDs; the same ID arriving a second time means the car leaves; print the lot occupancy (sorted IDs) after each event.", "nums_nocount")
T(c, "Simulate the Josephus problem with n people (n = the integer) and every k-th elimination where k=3; print the elimination order and the survivor.", "small_int")
T(c, "Simulate a traffic light cycle: green 4, yellow 1, red 3 time units; print the state at each time step 0..n*3 as 'time: STATE'.", "small_int")
T(c, "Simulate a vending machine with coins 1, 5, 10, 25 and print the greedy change for amounts 1..n*7 step 13, one per line as a dict repr.", "small_int")
T(c, "Run a cellular automaton (rule 30) with a width of 31 and a single centre cell for n generations; print the rows using '#' and '.'.", "small_int")
T(c, "Run Langton's ant on a 15x15 torus for n*20 steps, starting in the centre facing up; print the final grid and the number of black cells.", "small_int")
T(c, "Run a rule-110 cellular automaton on a ring of 40 cells (single live cell at index 39) for n steps and print each generation.", "small_int")
T(c, "Print n rows of a Pascal triangle mod 2 (Sierpinski) centred, using '*' and spaces.", "small_int")
T(c, "Simulate a stack-based virtual machine where each line of input is an instruction ('push X', 'pop', 'size', 'peek') using the commands format; print the final stack bottom to top.", "commands")
T(c, "Run a tiny interpreter: ints are lines pushing; here use the stack commands but 'pop' prints the popped value; at the end print 'sum of remaining' and 'max of remaining'.", "commands")
T(c, "Simulate a text editor with undo: treat each line as 'push X' = type X, 'pop' = undo the last, 'peek' = print the current last char typed or 'none', 'size' prints the number of kept entries; at the end print the concatenation of kept entries.", "commands")
T(c, "Implement a simple Fraction-based calculator: for each pair of consecutive numbers a, b (from the list) print their quotient as a fraction in lowest terms using fractions.Fraction; skip zeros as divisors with 'div0'.", "nums_nocount")
T(c, "Compute exact rational sum of 1/x for the positive numbers (abs values, skip zeros) with Fraction and print it as 'num/den' and the float approximation with 10 decimals.", "nums_nocount")
T(c, "Use decimal.Decimal with precision 28 to compute the sum and product of the given numbers' inverses (1/x for non-zero absolute values), printing with 10 decimals via quantize.", "nums_nocount")
T(c, "Compute compound interest: initial 1000, rate given by (first number mod 10 + 1)% per period, for periods equal to the count of numbers; print each period's balance as a rounded float with 2 decimals.", "nums_nocount")
T(c, "Print the matrix chain multiplication minimum scalar multiplications for dimension list = the absolute values of the numbers (+1 each, so no zeros).", "pos_nums")
T(c, "Print the maximum number of coins collected: given the numbers as balloons, solve the burst balloons problem (maximum coins) for the first 12 numbers.", "pos_nums")

# ---- error handling / classes / generators -------------------------------------------------------------
c = "errors_classes"
T(c, "For each line try to convert to int; collect ValueError messages and print the message text of the first failing line (use str(exception)), then the total of successfully parsed numbers.", "opt_ints_lines")
T(c, "Compute 100 divided by each line's integer value; catch ZeroDivisionError and ValueError separately, print 'zero', 'bad' or the quotient with 2 decimals.", "opt_ints_lines")
T(c, "Write a function that returns the element at index = value in a list [10,20,30,40]; catch IndexError and TypeError; print the result or the exception class name.", "opt_ints_lines")
T(c, "Use a custom exception hierarchy (BaseAppError, ParseError, RangeError) for validating lines: ints must be 1..5; print which error was raised; use finally to count processed lines.", "opt_ints_lines")
T(c, "Process the lines with a generator pipeline: read -> filter ints -> square -> running sum; print the running sums using next() and a for loop; a StopIteration-safe version too.", "opt_ints_lines")
T(c, "Use dict.get, setdefault and KeyError handling: build counts of tokens; look up the keys '5', '0', '-3', '2' and print each result or 'missing' via try/except KeyError.", "opt_ints_lines")
T(c, "Use a context manager class with __enter__/__exit__ to wrap each line's processing: print 'enter', the result and 'exit', and swallow ValueErrors printing 'swallowed'.", "opt_ints_lines")
T(c, "Raise and catch exceptions chained with 'raise ... from ...' when parsing; print the repr of the exception's __cause__ for the first bad line, or 'all ok'.", "opt_ints_lines")
T(c, "Write a retry function that calls an operation which fails on specific values (the first two attempts fail for each number divisible by 3, implemented with a counter); print how many attempts each number needed.", "nums_nocount")
T(c, "Implement a Matrix class with __add__, __mul__, __eq__, __repr__ and __getitem__ (dimensions from the input), then print A+A, A*A (when square), and A==A.", "square_matrix")
T(c, "Define a Vector2D class with operator overloading (+, -, * scalar, abs, ==, iteration) and process the points: print the sum, the vector with the largest norm, and the dot products of consecutive points.", "points")
T(c, "Define a dataclass Employee(name, dept, salary, age) with order=True, field defaults and __post_init__ validation; read the CSV into Employee objects, print sorted by default dataclass ordering, the first 5.", "csv_table")
T(c, "Define a class hierarchy Shape -> Rect, Circle, Triangle using abstract methods; build shapes from the triangle side lines (as triangles) and print the area and perimeter with 3 decimals via polymorphism.", "tri_sides")
T(c, "Define a Stack class with a generic type annotation using typing.Generic; process the commands; print results; use __len__ and __iter__ and __bool__.", "commands")
T(c, "Implement an iterator class with __iter__ and __next__ that yields running averages of the numbers; print the first 10 with 2 decimals; then use a generator expression for the same.", "nums_nocount")
T(c, "Implement a generator fibonacci() and itertools.islice; print the first n Fibonacci numbers, and the first one over 10**6, using a for loop with break.", "small_int")
T(c, "Implement a memoising decorator with functools.wraps and apply it to a recursive function counting paths in an n by n grid; print the result and cache hit counts.", "small_int")
T(c, "Use functools.lru_cache on a recursive partition function p(n,k) and print p(n,n) for n and cache_info() hits/misses.", "small_int")
T(c, "Use functools.reduce with a lambda to compute the product, the gcd and the string concatenation of the numbers; print all three.", "pos_nums")
T(c, "Use itertools: print combinations of 2 of the first 6 numbers, permutations of the first 3, the product of [0,1] repeated 3, accumulate (running sum) and chain of two lists.", "pos_nums")
T(c, "Use itertools.groupby on the sorted words by first letter; print letter, count and the group's words joined with '/'.", "words_line")
T(c, "Use itertools.takewhile and dropwhile with the predicate x < 50 on the numbers; print both lists; also use itertools.pairwise to print consecutive differences.", "pos_nums")
T(c, "Use itertools.product to enumerate all strings over 'ab' of length 3, and itertools.cycle with islice to print the first 7 words of the input cycled twice.", "words_line")
T(c, "Use enumerate with start=1, zip, map, filter, any, all and sum with generator expressions on the numbers; print one result per line, labelled.", "pos_nums")
T(c, "Implement a simple event system: observers registered in a dict of lists; for each number emit an event ('even' or 'odd') and print the handler outputs in registration order.", "pos_nums")
T(c, "Implement a state machine using an Enum (IDLE, RUNNING, DONE, ERROR) that transitions on each numeric token (even = advance, odd = error, zero = reset); print state names after each token.", "opt_ints_lines")
T(c, "Use enum.IntEnum and enum.Enum members for grades; map student grades to them and print sorted by enum value, the member names and values.", "student_records")
T(c, "Use typing.NamedTuple for a Record(name, grade, age, score); print the max score record using repr, and records as tuples via _asdict().", "student_records")
T(c, "Use a class with __slots__ and a classmethod/staticmethod factory to build objects from lines of students; print their str() and sorted by property computed score bucket.", "student_records")
T(c, "Implement a linked list class with append, reverse and a merge of two sorted lists; read the numbers, build two lists from the first and second halves (each sorted), merge, print.", "nums")
T(c, "Implement a doubly-ended queue using two stacks and process alternate pushes to front/back and pops; print the final order and the sum.", "nums")
T(c, "Implement a binary heap-based priority queue class with a task list: push (priority, name) tuples built from the strings with priority = length; pop all; print them in order.", "strings_n")
T(c, "Implement a simple tokenizer class with a regex, state, and peek/next methods for the expression lines; print token types and values.", "expr_lines")
T(c, "Implement a Counter-like class via dict subclass with __missing__; count words; print the top 3 with ties alphabetical; make sure printing the subclass instance works via dict repr sorted.", "words_line")
T(c, "Use string formatting widely: for each number print f-strings with width, fill, sign, hex, binary, percent, exponent and comma formats on one line.", "pos_nums")
T(c, "Use the % operator and str.format as well as f-strings to print the same data; for each (name, score) pair print three formatting styles.", "name_scores")
T(c, "Print using the sep and end arguments of print and sys.stdout.write; write the numbers separated by ', ' on one line, then the rest by sys.stdout.write with explicit newlines; finish with a final line using print(*items, sep='|').", "pos_nums")
T(c, "Write errors to stderr via sys.stderr for invalid lines and normal results to stdout; print on stdout only the valid integers' sum; exit with status 0.", "opt_ints_lines")
T(c, "Call sys.exit(2) after printing the count of valid lines when any line is invalid, else exit normally with status 0.", "opt_ints_lines")
T(c, "Raise an uncaught exception at the end if the sum of valid integers is negative (print the sum first); otherwise print 'fine'.", "opt_ints_lines")
T(c, "Use assert statements to check invariants on the input (the sorted list is non-decreasing) and print 'asserts ok'; additionally print the result of an assert False caught as AssertionError with its message.", "nums")
T(c, "Use the walrus operator, match statements (structural pattern matching) and f-string '=' specifiers to classify each number as 'neg', 'zero', 'small', 'large'; print them.", "nums")
T(c, "Use pattern matching (match/case) on the parsed command tuples (e.g., ('push', n), ('pop',)) of the stack commands and print the results.", "commands")
T(c, "Use nested functions and closures with nonlocal to build counters; call them for each token and print the counts; also use a lambda in a loop with default-argument binding to demonstrate late binding.", "words_line")
T(c, "Use *args, **kwargs, keyword-only parameters, default mutable argument avoidance and unpacking in calls; process the numbers; print the stats via a function returning a dict printed with sorted keys.", "nums")
T(c, "Use slicing extensively: print a[::2], a[::-1], a[1:-1], a[-3:], and assign slices (a[1:3] = [0]) and delete slices (del a[::2]); print the lists after each step.", "nums")
T(c, "Use list comprehension, dict comprehension, set comprehension and nested comprehensions to build outputs from the numbers; print each result labelled.", "nums")
T(c, "Use the bit-manipulation operators: print for each number (abs) the result of n & (n-1), n & -n, n ^ (n >> 1), and the bit length; also count the numbers that are powers of two.", "nums")
T(c, "Use integer/float conversions: print int(x) truncation, round half-to-even results for x.5 cases, and the repr of 0.1+0.2 and the sum of 0.1 ten times; plus the input numbers divided by 3 using repr.", "nums")
T(c, "Use math functions: print sqrt, log2 (for positive), sin and cos in radians (3 decimals) for each of the first 8 absolute numbers plus 1; and math.hypot, math.gcd and math.isqrt.", "nums")
T(c, "Use string methods split/partition/rpartition/join/replace/find/rfind/count/startswith/endswith/zfill/translate with str.maketrans on each line and print the results.", "text_lines")
T(c, "Use the bytes and bytearray types: encode each line in UTF-8, print the bytes repr, the hex string, the length, and decode back to check equality.", "text_uni")
T(c, "Use int.from_bytes and to_bytes on the numbers (abs, big-endian, minimal length) and print the byte lists; also struct.pack('>I') for those under 2**32.", "big_ints")
T(c, "Use heapq with tuples (priority, counter, item) to implement a stable priority queue; push the words with priority = length; pop all; print.", "strings_n")
T(c, "Use bisect.insort to maintain a sorted list as numbers arrive; print the median after each arrival.", "nums_nocount")
T(c, "Use array-like data with the 'array' module of type 'i' to store the numbers, then print the typecode, itemsize, the byteswapped first element, and the sum.", "nums_nocount")
T(c, "Use collections.ChainMap and a dict merge operator (|) to combine default settings with overrides from the lines 'word number'; print the combined dict sorted by key.", "pairs_str_int")
T(c, "Use collections.OrderedDict and move_to_end to implement a most-recently-used list of the words; print the order after each word and the final list.", "words_line")
T(c, "Use a deque with rotate and maxlen=5 to process the numbers; print the deque after each element and the sum of the final deque.", "nums_nocount")
T(c, "Use the statistics module: mean, median, mode (if unique else 'multi'), pstdev and stdev (3 decimals; if n < 2 print 'n/a').", "nums")
T(c, "Use fractions.Fraction and the limit_denominator method to approximate each float with denominator <= 100; print 'num/den'.", "floats")
T(c, "Use the string module constants and str.translate: remove punctuation from text and count ASCII letters/digits; print the result.", "text_lines")
T(c, "Use textwrap and str.splitlines(keepends=True) and print repr of each; also print the number of lines per splitlines vs split('\\n').", "text_lines")
T(c, "Use datetime/timedelta: for each time HH:MM add 90 minutes and print the new time (wrap at midnight) and day offset +0/+1.", "times")
T(c, "Use calendar and datetime: for each date print whether it is in a leap year, days in the month, and the date of the last day of that month.", "dates")
T(c, "Use time arithmetic: sum all HH:MM times as durations (not clock times) and print the total as 'H:MM' with hours possibly above 24.", "times")
T(c, "Use unicodedata: print the category, name (or 'unnamed') and NFC/NFD lengths of each distinct non-ASCII character in the text; sort by code point.", "text_uni")
T(c, "Use sorted(set(...)) over characters and print the characters whose code point is above 127 with their codes in decimal, the total count and the max.", "text_uni")
T(c, "Use string slicing and indexing on non-ASCII text: print the first 3 characters, last 3 characters, every second character, and s[::-1] for the first non-empty line.", "text_uni")
T(c, "Use the str methods isalpha, isdigit, isupper, islower, istitle on each word and print the booleans as a string like 'TFFTF'.", "words_line_uni")
T(c, "Use ljust/rjust/center on non-ASCII words with width 8 and fill '_' and also print the len of the results; check that padding counts characters.", "words_line_uni")
T(c, "Count words, characters, and bytes (like wc) for the input text; print three numbers on a line like the wc -l -w -c output with width 7.", "text_uni")
T(c, "Print the word counts of the text where words are lowercased with casefold and non-alphabetic edge characters stripped (str.strip with string.punctuation); sort by count desc then word; first 8 lines.", "text_uni")
T(c, "Detect and print the longest line (in characters) with its 1-based number, and the shortest non-empty line; ties first.", "text_uni")
T(c, "Take the word with the most characters per UTF-8 byte (lowest bytes/chars ratio first) and print it with its ratio to 3 decimals; print the ASCII ratio for the whole text.", "words_line_uni")
T(c, "Print the base-2 logarithm table: for the numbers print the position of the highest set bit via bit_length, and the representation of -n in two's complement with 16 bits for small n.", "nums")
