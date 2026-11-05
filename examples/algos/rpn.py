"""Tokenizer and shunting-yard evaluator for generated integer expressions."""
import sys

SMALL = "--small" in sys.argv
COUNT = 120 if SMALL else 90_000
DEPTH = 2 if SMALL else 4

seed = 5150


def rnd():
    global seed
    seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
    return seed


def tokenize(source):
    tokens = []
    number = ""
    for ch in source:
        if ch.isdigit():
            number += ch
        else:
            if number:
                tokens.append(number)
                number = ""
            if ch != " ":
                tokens.append(ch)
    if number:
        tokens.append(number)
    return tokens


PRECEDENCE = {"+": 1, "-": 1, "*": 2, "^": 3}
RIGHT = {"^"}


def to_rpn(tokens):
    output = []
    stack = []
    for token in tokens:
        if token.isdigit():
            output.append(token)
        elif token == "(":
            stack.append(token)
        elif token == ")":
            while stack and stack[-1] != "(":
                output.append(stack.pop())
            stack.pop()
        else:
            while stack and stack[-1] != "(":
                top = stack[-1]
                if top in RIGHT:
                    higher = PRECEDENCE[top] > PRECEDENCE[token]
                else:
                    higher = PRECEDENCE[top] >= PRECEDENCE[token]
                if not higher:
                    break
                output.append(stack.pop())
            stack.append(token)
    while stack:
        output.append(stack.pop())
    return output


def evaluate(rpn):
    stack = []
    for token in rpn:
        if token.isdigit():
            stack.append(int(token))
        else:
            right = stack.pop()
            left = stack.pop()
            if token == "+":
                stack.append(left + right)
            elif token == "-":
                stack.append(left - right)
            elif token == "*":
                stack.append(left * right)
            else:
                stack.append(left ** right)
    return stack[0]


def expression(depth):
    if depth == 0 or rnd() % 3 == 0:
        return str(1 + rnd() % 20)
    operator = ["+", "-", "*"][rnd() % 3]
    return "(" + expression(depth - 1) + " " + operator + " " + expression(depth - 1) + ")"


total = 0
for index in range(COUNT):
    source = expression(DEPTH)
    value = evaluate(to_rpn(tokenize(source)))
    total += value
    if index < 3:
        print("expr", index, value)

print("count", COUNT)
print("checksum", total)

big = "2 ^ 70"
print("big", evaluate(to_rpn(tokenize(big))))
