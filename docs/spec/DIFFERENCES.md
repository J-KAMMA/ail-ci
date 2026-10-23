# Differences from CPython 3.12

| id | difference |
| --- | --- |
| C?-job-fuzz82-10231553-1 | A function that deletes an item of a module-level numeric list (`del xs[i]`) is refused by name on the typed path. Before, deleting the last item printed the unchanged list (the write through the `const` table was dropped) and deleting an earlier item crashed; the default build falls back to the general path and matches CPython. |
