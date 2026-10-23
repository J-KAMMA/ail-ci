# Differences from CPython

| Id | Area | Description |
| --- | --- | --- |
| C?-job-fuzz90-10231630-1 | identity | `is` / `is not` on equal strings or bytes can depend on where each value was made; a visible pair is refused by name instead of answering False. |
