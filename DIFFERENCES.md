# Differences from CPython

| Id | Area | Description |
| --- | --- | --- |
| C?-job-fuzz90-10231630-1 | identity | `is` / `is not` on equal text can depend on where each value was made (CPython merges constants and shares the empty and one-character str/bytes); a visible pair is refused by name instead of answering False. Unequal bytes, mutable `bytearray` and longer values built at run time answer as CPython does. |
