# advparse: a text-adventure command parser built by AIL

`advparse.py` is an ordinary Python 3.12 program of about 300 lines. It reads one command per
line from standard input, echoes each line as `> line`, and prints the reply. It exits 0 at
`quit` or at end of input; if the locked door is opened without the brass key it prints
`the door will not move.` and exits 3.

## The world

The world is built in code from three classes, `Room`, `Item` and `Player`:

- six rooms: hall (start), kitchen, garden, cellar, library and vault;
- eight items: brass key, iron key, lamp, coin, apple, book, rope and sword;
- two containers: a chest in the kitchen and a cabinet in the library.

The hall has a locked door west to the vault. A brass key is inside the cabinet. Items score
10 (coin) or 5 (brass key, lamp, book); each new room scores 5, for a maximum of 50.
A command after `quit` is never read.

## The parser

Each line is lowercased, split on spaces, and the articles `a`, `an` and `the` are dropped.
Blank lines are echoed but do nothing. Verbs and synonyms:

| verb | synonyms | notes |
| --- | --- | --- |
| `go` | `walk`, `n` `s` `e` `w` `u` `d`, `north` ... | one room per move |
| `take` | `get`, `pick up` | from the room or an open container |
| `drop` | | from the inventory |
| `put X in Y` | | Y must be an open container in the room |
| `open`, `close` | | containers and the door |
| `look` | `l` | room, items and exits |
| `examine` | `x` | items, containers and the door |
| `inventory` | `i` | carried items |
| `score` | | `score S of 50 in M moves` |
| `quit` | | prints the score and exits 0 |

Adjectives pick one of two items: `brass key` and `iron key` are distinct, while a bare `key`
prints `which do you mean, the brass key or the iron key?`. `it` means the last item named.
Unknown verbs, unknown nouns, missing objects and closed containers each have one clear reply.

## Build and run

```sh
python3 AIL_CURRENT/ail_chatgpt.py compile examples/advparse/advparse.py -o /tmp/advparse
/tmp/advparse < examples/advparse/scripts/win.txt
python3 examples/advparse/advparse.py < examples/advparse/scripts/win.txt
```

The scripts in `scripts/` are 15-27 commands each: `win.txt` (a winning run, score 50),
`synonyms.txt` (every synonym), `ambiguous.txt` (the two keys and `it`), `containers.txt`
(open, close, put and closed-container rules), `errors.txt` (every error message),
`spacing.txt` (blank lines, extra spaces, upper case), `quiet.txt` (end of input, no `quit`)
and `locked.txt` (the door without the key, exit 3).

## Results

`RESULTS.md` records the build path and the comparison with CPython for every script in the
default build and with `AIL_UNIFIED_FORCE=1`.
