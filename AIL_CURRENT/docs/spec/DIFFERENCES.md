# Differences from CPython

| id | area | difference | status |
| --- | --- | --- | --- |
| C?-job-fuzz20-10230625-1 | int.from_bytes | the general path accepted int and None as the bytes source (int 1 became one zero byte, None became empty) | fixed: both now raise TypeError like CPython |
| C?-job-pre24-10240316-1 | class value __name__ | `C.__name__` raised AttributeError on both builds (also through an argument, a list item, an instance attribute or a dict value) | fixed: the class-statement name is returned, including when the class body assigns `__name__`; a shadowing local/parameter or a module-scope rebinding is respected, and an own-name read in the class body raises NameError |
