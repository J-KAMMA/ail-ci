# Differences from CPython

| id | area | difference | status |
| --- | --- | --- | --- |
| C?-job-fuzz20-10230625-1 | int.from_bytes | the general path accepted int and None as the bytes source (int 1 became one zero byte, None became empty) | fixed: both now raise TypeError like CPython |
| C?-job-pre15-10240045-1 | assert | `assert False, 42` put the string `'42'` in `e.args` instead of the integer 42 (numeric messages were stringified before the AssertionError was built) | fixed: both paths keep the message value for `e.args`; uncaught text is unchanged |
