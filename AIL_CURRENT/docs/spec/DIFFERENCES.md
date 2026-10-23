# Differences from CPython

| id | area | difference | status |
| --- | --- | --- | --- |
| C?-job-pre23-10240315-1 | bytes / str codecs | tab- and colon-normalized encoding names such as `utf\t8` and `iso-8859-1:1987` raised LookupError (literal names were also refused at compile time) instead of naming CPython's UTF-8 / Latin-1 | fixed: names are normalized like `encodings.normalize_encoding`; the runtime and both compile-time checks use the same alias table |
| C?-job-fuzz20-10230625-1 | int.from_bytes | the general path accepted int and None as the bytes source (int 1 became one zero byte, None became empty) | fixed: both now raise TypeError like CPython |
