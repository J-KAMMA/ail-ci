package main

import (
	"fmt"
	"io"
	"os"
	"sort"
	"strconv"
	"strings"
)

func main() {
	data, _ := io.ReadAll(os.Stdin)
	totals := make(map[string]int64)
	for _, line := range strings.Split(string(data), "\n") {
		if line == "" {
			continue
		}
		parts := strings.SplitN(line, ",", 2)
		value, _ := strconv.ParseInt(parts[1], 10, 64)
		totals[parts[0]] += value
	}
	keys := make([]string, 0, len(totals))
	for key := range totals {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	for _, key := range keys {
		fmt.Printf("%s,%d\n", key, totals[key])
	}
}
