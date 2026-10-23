# Differences from CPython 3.12

| id | status | area | summary |
| --- | --- | --- | --- |
| C?-job-fuzz61-10231419-1 | fixed | string encoding | A run-time encoding name used to accept only a few spellings of utf-8, ascii and latin-1, so aliases reached through a variable, argument, list item, attribute or dict value raised `LookupError`. Every alias from `encodings.aliases` for those three codecs is now accepted on both builds. |
| C?-job-fuzz61-10231419-2 | open | string encoding | A run-time name of a codec outside utf-8/ascii/latin-1 (for example `cp1252`, `utf-8-sig`, `utf-16`) raises `LookupError` where CPython encodes or decodes. The same name written as a literal is refused at compile time by name. |
| C?-job-fuzz61-10231419-3 | open | string encoding | `b"".decode(name)` looks the codec up and raises `LookupError` for an unknown name; CPython returns `b""` without looking it up. `"".encode(name)` does validate the name in both. |
| C?-job-fuzz61-10231419-4 | open | exceptions | `UnicodeEncodeError` / `UnicodeDecodeError` values do not expose `.encoding`, `.object`, `.start`, `.end` or `.reason`. |
