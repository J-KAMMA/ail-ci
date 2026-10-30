# ledger_bin

Write a command-line program:

    prog FILE

FILE is the path to a binary file in the "LXF" ledger format described below. The program checks
the structure of the whole file, replays the ledger operations in file order, and prints a
summary.

## Building blocks

- `u8`: one byte.
- `var`: an unsigned integer in a variable-length encoding. Each byte carries 7 value bits (its
  low 7 bits), least significant group first; a byte with the high bit (0x80) set means another
  byte follows. Rules:
  - at most 5 bytes; if the 5th byte has its high bit set, that is an error (`varint`);
  - the value must be at most 4294967295 (2^32 - 1), otherwise `varint`;
  - the encoding must be the shortest one: a varint of 2 or more bytes whose last byte is `00` is
    an error (`varint`). So `00` is 0, `7F` is 127, `80 01` is 128, and `80 00` is invalid.
- `check`: one byte, explained below.

## File layout

- Header, 6 bytes: `C7 4C 58 46` (the byte 0xC7 followed by ASCII `LXF`), a version byte that must
  be `02`, and a flags byte. Only bit 0 of the flags byte may be set (flags is `00` or `01`).
  Bit 0 set means *strict mode* (see below).
- Then zero or more records, back to back, until the end of the file.

Each record is: an opcode byte, a body that depends on the opcode, and a check byte.

| opcode | name | body |
|---|---|---|
| `01` | OPEN | `id: var`, `name_len: u8`, `name: name_len bytes`, `initial: var` |
| `02` | MOVE | `from: var`, `to: var`, `amount: var` |
| `03` | SHUT | `id: var` |
| `04` | MINT | `id: var`, `amount: var` |
| `05` | NOTE | `len: var`, then `len` bytes of arbitrary content |

- `name_len` must be 1 .. 32 and every name byte must be 0x21 .. 0x7E (printable ASCII without
  space); otherwise `name`.
- The check byte is computed over all bytes of the record before it (opcode and body):
  start with c = 0 and for each byte b do c = (c * 31 + b) mod 251. The check byte must equal
  the final c; otherwise `check`.

## Structural errors

The file is read from the start, one byte at a time, and the *first* problem encountered stops
the program. Problems are checked in the order the bytes are read:

1. File shorter than 6 bytes, wrong magic, wrong version, or invalid flags: `header`, offset 0.
2. For each record, at its start offset X:
   - an opcode other than `01`..`05`: `opcode`;
   - each field in body order: a `var` is read byte by byte (end of file inside it:
     `truncated`; a 5th byte with the high bit set: `varint`) and, once complete, checked for
     shortest form and range (`varint`); for OPEN the `name_len` byte is checked as soon as it
     is read (`name`, or `truncated` if the file ends before it), then the name bytes one by one
     (`truncated` if the file ends, `name` for a bad byte); for NOTE, if fewer than `len` bytes
     remain: `truncated`;
   - then the check byte (`truncated` if the file ends before it, `check` if it is wrong).

On a structural error print exactly one line

    error at offset X: KIND

where KIND is one of `header`, `opcode`, `varint`, `name`, `truncated`, `check`, and X is the
decimal byte offset of the start of the record being read (0 for `header`). Nothing else is
printed (no summary), and the exit status is 2.

The whole file is checked for structural errors before anything else is printed; a structural
error anywhere means no summary.

## Replaying the ledger

Accounts are identified by their `id` (any value 0 .. 2^32-1). An account is *open* after a
successful OPEN and *shut* after a successful SHUT; it never comes back. Balances are integers that
never become negative (they fit in a signed 64-bit integer for all valid inputs).

A record that breaks one of the following rules is *rejected*: it has no effect except being
counted under the first reason that applies, checked in the order listed.

- OPEN: `dup` if an account with this id exists (open or shut). Otherwise a new open account with
  that name and balance `initial`.
- MOVE: `unknown` if `from` does not exist, then `unknown` if `to` does not exist; `shut` if
  `from` is shut, then `shut` if `to` is shut; `self` if `from` = `to`; `funds` if `amount` is
  larger than the balance of `from`. Otherwise `amount` moves from `from` to `to` (an amount of 0
  is fine).
- SHUT: `unknown` if the account does not exist; `shut` if it is already shut. Otherwise it is
  shut (its balance is kept).
- MINT: `unknown`, then `shut` as for SHUT. Otherwise `amount` is added to the balance.
- NOTE: never rejected and has no effect.

**Strict mode** (flags bit 0 set): the first rejection stops the program instead. Print exactly
one line `rejected at offset X: REASON` (X = start offset of the record, REASON one of `dup`,
`unknown`, `shut`, `self`, `funds`) and nothing else, exit status 3. (Structural errors are found
first: a file with a structural error always gives the `error at offset` line, even if an earlier
record would be rejected.)

## Output on success (exit status 0)

    records: R
    accounts: A open, S shut
    rejected: dup=D unknown=U shut=H self=F funds=N
    total: T
    top: ID NAME BALANCE      (0 to 5 lines)
    digest: G

- R: number of records in the file (all opcodes, including rejected ones and NOTEs).
- A, S: numbers of open and of shut accounts at the end.
- D, U, H, F, N: rejection counts per reason.
- T: sum of the balances of all accounts (open and shut).
- `top` lines: the open accounts with the largest balances, at most 5, ordered by balance
  descending, ties by id ascending. Shut accounts are never listed here. Each line is
  `top: ` followed by id, name and balance separated by single spaces.
- G: a digest over all accounts (open and shut) in ascending id order: start with g = 0 and for each
  account do g = (g * 1000003 + id * 7 + balance) mod 1000000007. (All intermediate values
  fit in a signed 64-bit integer.)

All numbers are printed in decimal without padding, every line ends with `\n`.

## Other errors

Wrong number of arguments (exactly one is required) or an unreadable file: print nothing on
standard output, exit status 1.
