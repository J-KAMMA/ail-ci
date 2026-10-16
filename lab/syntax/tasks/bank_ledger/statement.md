# bank_ledger

Category: records / errors

Read standard input, write standard output, exit with status 0.

A single account starts with balance 0. Each input line is one command:
- `deposit N` adds N.
- `withdraw N` subtracts N; if N exceeds the balance, print `error: insufficient funds` and leave the balance unchanged.
- `balance` prints `balance B`.
- Any other command prints `error: unknown command`.

Keep the account in a record. Raising and catching an error for the failures is a natural fit but only the output matters.
