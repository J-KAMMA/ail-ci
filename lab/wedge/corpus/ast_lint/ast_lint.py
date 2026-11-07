"""Lint-like AST walk over nested tuples: nesting depth, node counts, name checks."""


def node_count(node: tuple) -> int:
    total = 1
    i = 0
    while i < len(node):
        child = node[i]
        if isinstance(child, tuple):
            total += node_count(child)
        i += 1
    return total


def max_depth(node: tuple) -> int:
    best = 0
    i = 0
    while i < len(node):
        child = node[i]
        if isinstance(child, tuple):
            d = max_depth(child) + 1
            if d > best:
                best = d
        i += 1
    return best


def count_tag(node: tuple, tag: str) -> int:
    total = 0
    i = 0
    while i < len(node):
        child = node[i]
        if isinstance(child, str):
            if child == tag:
                total += 1
        elif isinstance(child, tuple):
            total += count_tag(child, tag)
        i += 1
    return total


def count_ints(node: tuple) -> int:
    total = 0
    i = 0
    while i < len(node):
        child = node[i]
        if isinstance(child, int):
            total += 1
        elif isinstance(child, tuple):
            total += count_ints(child)
        i += 1
    return total


def sum_ints(node: tuple) -> int:
    total = 0
    i = 0
    while i < len(node):
        child = node[i]
        if isinstance(child, int):
            total += child
        elif isinstance(child, tuple):
            total += sum_ints(child)
        i += 1
    return total


def leaves(node: tuple) -> int:
    seen = 0
    i = 0
    while i < len(node):
        child = node[i]
        if isinstance(child, tuple):
            seen += leaves(child)
        else:
            seen += 1
        i += 1
    return seen


def has_tag(node: tuple, tag: str) -> bool:
    i = 0
    while i < len(node):
        child = node[i]
        if isinstance(child, str):
            if child == tag:
                return True
        elif isinstance(child, tuple):
            if has_tag(child, tag):
                return True
        i += 1
    return False
