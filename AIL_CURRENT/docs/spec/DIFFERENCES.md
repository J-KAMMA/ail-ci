# Differences from CPython

| id | area | difference | status |
| --- | --- | --- | --- |
| C?-job-fuzz20-10230625-1 | int.from_bytes | the general path accepted int and None as the bytes source (int 1 became one zero byte, None became empty) | fixed: both now raise TypeError like CPython |
| C?-job-pre20-10240301-1 | chr() | the general path stores 16-bit strings and cannot represent a non-BMP code point; a literal argument is refused at build time and a runtime value stops with `AIL limit: chr_non_bmp` (the typed/default path matches CPython) | declared: named refusal (was an internal error) |
