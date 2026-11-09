package main

import (
	"fmt"
	"io"
	"os"
	"sort"
	"strings"
)

const maxAmount int64 = 1000000000000

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
	data, _ := io.ReadAll(os.Stdin)

	balances := make(map[string]int64)
	bad := 0

	for _, line := range strings.Split(string(data), "\n") {
		fields := strings.Fields(line)
		if len(fields) == 0 {
			continue
		}
		if len(fields) < 3 {
			bad++
			continue
		}

		amount, ok := parseAmount(fields[1])
		if !ok {
			bad++
			continue
		}

		payer := fields[0]
		participants := fields[2:]

		seen := make(map[string]bool, len(participants))
		duplicate := false
		for _, p := range participants {
			if seen[p] {
				duplicate = true
				break
			}
			seen[p] = true
		}
		if duplicate {
			bad++
			continue
		}

		k := int64(len(participants))
		q := amount / k
		r := amount % k

		balances[payer] += amount
		for i, p := range participants {
			owed := q
			if int64(i) < r {
				owed++
			}
			balances[p] -= owed
		}
	}

	names := make([]string, 0, len(balances))
	var total int64
	for name, balance := range balances {
		names = append(names, name)
		total += balance
	}
	sort.Strings(names)

	var out strings.Builder
	fmt.Fprintf(&out, "bad %d\n", bad)
	for _, name := range names {
		fmt.Fprintf(&out, "balance %s %d\n", name, balances[name])
	}
	fmt.Fprintf(&out, "total %d\n", total)
	fmt.Print(out.String())
}
