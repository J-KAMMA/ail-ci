package main

import (
	"bufio"
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
	reader := bufio.NewReaderSize(os.Stdin, 1<<16)
	writer := bufio.NewWriter(os.Stdout)
	defer writer.Flush()

	bal := make(map[string]int64)
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

		bal[payer] += amt
		for i, p := range parts {
			owe := q
			if int64(i) < r {
				owe++
			}
			bal[p] -= owe
		}
	}

	for {
		line, err := reader.ReadString('\n')
		if line != "" {
			process(line)
		}
		if err != nil {
			if err != io.EOF {
				break
			}
			break
		}
	}

	fmt.Fprintf(writer, "bad %d\n", bad)

	names := make([]string, 0, len(bal))
	for name := range bal {
		names = append(names, name)
	}
	sort.Strings(names)
	for _, name := range names {
		fmt.Fprintf(writer, "balance %s %d\n", name, bal[name])
	}
	fmt.Fprintf(writer, "total 0\n")
}
