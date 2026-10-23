# Differences from CPython

| id | area | difference | status |
| --- | --- | --- | --- |
| C?-job-pre25-10240322-1 | dict(mapping) | a keys()/__getitem__ object without __iter__ was iterated as pairs (dict(m) raised TypeError; keys() disagreeing with __iter__ took the wrong one) | fixed: dict(m), dict.update(m) and defaultdict(factory, m) follow the mapping protocol when keys() is present |
| C?-job-fuzz20-10230625-1 | int.from_bytes | the general path accepted int and None as the bytes source (int 1 became one zero byte, None became empty) | fixed: both now raise TypeError like CPython |
