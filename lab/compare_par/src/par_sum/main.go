// par_sum: sum over n in 1..N of steps(n) * (n % 7 - 3) on 4 goroutines with per-thread partial sums.
package main

import (
	"bufio"
	"fmt"
	"os"
	"sync"
)

const nthreads = 4

func add(a, b int64) int64 {
	r := a + b
	if (b > 0 && r < a) || (b < 0 && r > a) {
		fmt.Fprintln(os.Stderr, "OverflowError: integer overflow in + (ints are 64-bit; --exact-int gives exact ints)")
		os.Exit(1)
	}
	return r
}

func steps(m int64) int64 {
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
	var n int64
	if _, err := fmt.Fscan(in, &n); err != nil || n < 0 {
		os.Exit(1)
	}
	if n == 0 {
		fmt.Println(0)
		return
	}
	threads := n
	if threads > nthreads {
		threads = nthreads
	}
	chunk := (n + threads - 1) / threads
	parts := make([]int64, threads)
	var wg sync.WaitGroup
	started := int64(0)
	for t := int64(0); t < threads; t++ {
		lo := t*chunk + 1
		hi := lo + chunk - 1
		if lo > n {
			break
		}
		if hi > n {
			hi = n
		}
		wg.Add(1)
		go func(slot int64, lo, hi int64) {
			defer wg.Done()
			var acc int64
			for k := lo; k <= hi; k++ {
				acc = add(acc, steps(k)*(k%7-3))
			}
			parts[slot] = acc
		}(started, lo, hi)
		started++
	}
	wg.Wait()
	var total int64
	for _, v := range parts[:started] {
		total = add(total, v)
	}
	fmt.Println(total)
}
