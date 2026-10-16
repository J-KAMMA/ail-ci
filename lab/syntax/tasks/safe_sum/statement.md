# safe_sum

Category: errors

Read standard input, write standard output, exit with status 0.

Split the whole input on whitespace. Each token is either a decimal integer (optional leading `-`, then digits) or garbage. For each garbage token, in input order, print `bad: TOKEN`. Finally print `sum=S`, the sum of the valid integers. The program must not crash on garbage.

Example: input `10 abc -4` gives `bad: abc` then `sum=6`.
