package main

import (
	"bufio"
	"fmt"
	"os"
	"sort"
	"strings"
)

const maxAmount = 1000000000000

func parseAmount(s string) (int64, bool) {
	if len(s) == 0 {
		return 0, false
	}
	var v int64
	for i := 0; i < len(s); i++ {
		c := s[i]
		if c < '0' || c > '9' {
			return 0, false
		}
		v = v*10 + int64(c-'0')
		if v > maxAmount {
			return 0, false
		}
	}
	return v, true
}

func main() {
	balances := make(map[string]int64)
	bad := 0

	process := func(line string) {
		f := strings.Fields(line)
		if len(f) == 0 {
			return
		}
		if len(f) < 3 {
			bad++
			return
		}
		amt, ok := parseAmount(f[1])
		if !ok {
			bad++
			return
		}
		parts := f[2:]
		seen := make(map[string]bool, len(parts))
		for _, p := range parts {
			if seen[p] {
				bad++
				return
			}
			seen[p] = true
		}
		payer := f[0]
		k := int64(len(parts))
		q := amt / k
		r := amt % k
		balances[payer] += amt
		for i, p := range parts {
			owe := q
			if int64(i) < r {
				owe++
			}
			balances[p] -= owe
		}
	}

	reader := bufio.NewReaderSize(os.Stdin, 1<<16)
	for {
		line, err := reader.ReadString('\n')
		if len(line) > 0 {
			process(line)
		}
		if err != nil {
			break
		}
	}

	w := bufio.NewWriter(os.Stdout)
	defer w.Flush()

	fmt.Fprintf(w, "bad %d\n", bad)

	names := make([]string, 0, len(balances))
	for name := range balances {
		names = append(names, name)
	}
	sort.Strings(names)

	var total int64
	for _, name := range names {
		b := balances[name]
		total += b
		fmt.Fprintf(w, "balance %s %d\n", name, b)
	}
	fmt.Fprintf(w, "total %d\n", total)
}
