package main

import (
	"bufio"
	"fmt"
	"os"
	"sort"
	"strconv"
	"strings"
)

func main() {
	reader := bufio.NewReaderSize(os.Stdin, 1<<20)
	balances := make(map[string]int64)
	bad := 0

	for {
		line, err := reader.ReadString('\n')
		if len(line) > 0 {
			processLine(line, balances, &bad)
		}
		if err != nil {
			break
		}
	}

	var names []string
	for name := range balances {
		names = append(names, name)
	}
	sort.Strings(names)

	var out strings.Builder
	fmt.Fprintf(&out, "bad %d\n", bad)
	var total int64
	for _, name := range names {
		fmt.Fprintf(&out, "balance %s %d\n", name, balances[name])
		total += balances[name]
	}
	fmt.Fprintf(&out, "total %d\n", total)

	os.Stdout.WriteString(out.String())
}

func processLine(line string, balances map[string]int64, bad *int) {
	fields := strings.FieldsFunc(line, func(r rune) bool {
		return r == ' ' || r == '\t' || r == '\n' || r == '\r'
	})
	if len(fields) == 0 {
		return
	}
	if len(fields) < 3 {
		*bad++
		return
	}

	amount, ok := parseAmount(fields[1])
	if !ok {
		*bad++
		return
	}

	participants := fields[2:]
	seen := make(map[string]bool, len(participants))
	for _, p := range participants {
		if seen[p] {
			*bad++
			return
		}
		seen[p] = true
	}

	k := int64(len(participants))
	q := amount / k
	r := amount % k

	balances[fields[0]] += amount
	for i, p := range participants {
		owe := q
		if int64(i) < r {
			owe++
		}
		balances[p] -= owe
	}
}

func parseAmount(s string) (int64, bool) {
	if len(s) == 0 {
		return 0, false
	}
	for i := 0; i < len(s); i++ {
		if s[i] < '0' || s[i] > '9' {
			return 0, false
		}
	}
	v, err := strconv.ParseInt(s, 10, 64)
	if err != nil {
		return 0, false
	}
	if v < 0 || v > 1000000000000 {
		return 0, false
	}
	return v, true
}

var _ = sort.Strings
