# DIFFERENCES

Known differences from CPython. New rows use `C?-<branch>-N` until a maintainer assigns an id.

| id | area | difference | status |
|----|------|------------|--------|
| C?-job-fuzz89-10231611-1 | bytes.split / bytes.rsplit | With a `None` separator and a reached `maxsplit`, the unsplit remainder lost its outer whitespace (`b" a ".split(None, 0)` gave `[b"a"]`; CPython gives `[b"a "]`, and the mirror case in `rsplit`). | fixed in safetyrt.py |
