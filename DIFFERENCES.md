# Differences from CPython (record)

| ID | Area | Status | Description |
| --- | --- | --- | --- |
| C?-job-fuzz65-10231438-1 | heapq / list repr | fixed | After a caught `heappush` TypeError on a `list[int]` (CPython appends before comparing), the annotation-specialized list repr printed a string element as `x` instead of `'x'` when a tuple comparison had generated that helper. Scalar elements now use the runtime value's `repr`. |
