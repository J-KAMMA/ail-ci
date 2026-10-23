# Differences from CPython

| id | area | difference | status |
| --- | --- | --- | --- |
| C?-job-fuzz20-10230625-1 | int.from_bytes | the general path accepted int and None as the bytes source (int 1 became one zero byte, None became empty) | fixed: both now raise TypeError like CPython |
| C?-job-pre22-10240312-1 | with / generators | a `with` whose body yields in the same function was built, but closing that generator never reached `__exit__` (CPython passes `GeneratorExit`) | refused by name at compile time (`with` around a `yield`) |
