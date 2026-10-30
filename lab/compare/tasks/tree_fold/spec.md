# tree_fold

Write a command-line program:

    prog

The program reads a weighted ordered tree and a list of operations from standard input, applies
the operations in order, and prints what the query operations ask for. It takes no arguments
(extra arguments are ignored).

## Input

Standard input is split into lines at `\n`; the `\n` after the last line is optional, and there
is no `\r` anywhere. Line 1 is the tree, every following line is one operation. There must be at
least the tree line; an empty line anywhere is malformed.

### Tree notation

    node     = name ":" weight [ "[" node { " " node } "]" ]
    name     = 1 to 16 lowercase letters a-z
    weight   = decimal integer 0 .. 1000000, written as "0" or without leading zeros

The children of a node are listed in order inside `[` `]`, separated by exactly one space. A node
without children has no brackets (`[]` is malformed). Line 1 must be exactly one node (the root)
with nothing before or after it. Names need not be unique. Example:

    top:5[left:3 mid:0[x:1 y:1] right:2]

The depth of the tree (the root has depth 0) is at most 5000 in every test input, and the input
has at most 3000000 nodes.

### Operations

| line | effect |
|---|---|
| `total` | print the sum of all weights |
| `stats` | print `nodes=<n> leaves=<l> height=<h> widest=<w>`: number of nodes, number of nodes without children, the largest depth of any node, the largest number of children of any node |
| `level D` | print `<count> <sum>`: the number of nodes at depth D and the sum of their weights (`0 0` if there are none) |
| `find NAME` | print the path to the first node named NAME in pre-order (a node before its children, children in their current order): the names from the root to that node joined by `/`; or `none` |
| `print` | print the tree in the notation above (names may contain `+` after `fold`) |
| `prune W` | remove every non-root node whose subtree weight (its weight plus the weights of all its descendants) is less than W, together with its whole subtree. Subtree weights are those of the tree before the operation |
| `sort` | reorder the children of every node by subtree weight descending, then by name ascending (byte-wise, a proper prefix first), keeping the current order for complete ties |
| `mirror` | reverse the order of the children of every node |
| `fold` | merge chains: see below |
| `cut NAME` | find the first node named NAME in pre-order; if it exists and is not the root, remove it and put its children, in their order, into its parent's child list at the position where it was. Otherwise nothing happens. Prints nothing |

- In operation lines the keyword and its argument are separated by exactly one space, and there is
  nothing else on the line. D and W are decimal integers 0 .. 10^15 without leading zeros
  (`0` itself is allowed). NAME is 1 or more characters from `a-z` and `+` (it may be longer than
  16, so that names created by `fold` can be found).
- `fold`: as long as some non-root node P has exactly one child C, replace P and C by a single node
  named `<P's name>+<C's name>` with weight P + C and C's children, in P's place. The result does
  not depend on the order of the merges: every maximal chain v1 - v2 - ... - vk, where v1 is not
  the root and each of v1 .. v(k-1) has exactly one child, becomes one node named
  `v1+v2+...+vk` (whose own name parts may already contain `+`). The root is never merged with its
  child (but its child can be merged with the grandchild).

## Output

Every printed value is one line ending with `\n`. Exit status 0.

If the input is malformed in any way (tree syntax, a name longer than 16 letters, a weight out of
range or with a leading zero, an unknown operation, a missing or extra argument, a bad number or
NAME, an empty line, `\r`): print nothing at all on standard output and exit with status 1. The
whole input is checked before any operation runs.
