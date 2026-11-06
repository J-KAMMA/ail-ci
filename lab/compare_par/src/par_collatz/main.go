// par_collatz: Collatz step counts for 1..N on W goroutines with contiguous chunks (see spec.md).
package main

import (
	"bufio"
	"fmt"
	"os"
	"sync"
)

func steps(m uint64) int64 {
	var c int64
	for m != 1 {
		if m&1 == 1 {
			m = 3*m + 1
		} else {
			m >>= 1
		}
		c++
	}
	return c
}

func main() {
	in := bufio.NewReaderSize(os.Stdin, 1<<16)
	var n, w int
	if _, err := fmt.Fscan(in, &n, &w); err != nil || n < 1 || w < 1 {
		os.Exit(1)
	}
	threads := w
	if threads > n {
		threads = n
	}
	res := make([]int64, n)
	chunk := (n + threads - 1) / threads
	var wg sync.WaitGroup
	for t := 0; t < threads; t++ {
		lo := t*chunk + 1
		hi := lo + chunk - 1
		if lo > n {
			break
		}
		if hi > n {
			hi = n
		}
		wg.Add(1)
		go func(lo, hi int) {
			defer wg.Done()
			for k := lo; k <= hi; k++ {
				res[k-1] = steps(uint64(k))
			}
		}(lo, hi)
	}
	wg.Wait()
	best := int64(-1)
	bestn := 0
	total := int64(0)
	for i, v := range res {
		total += v
		if v > best {
			best = v
			bestn = i + 1
		}
	}
	fmt.Printf("%d %d %d\n", best, bestn, total)
}
