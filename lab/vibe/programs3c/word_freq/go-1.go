package main

import (
	"bufio"
	"fmt"
	"io"
	"os"
	"sort"
)

func main() {
	data, _ := io.ReadAll(os.Stdin)

	counts := make(map[string]int)
	total := 0
	var buf []byte

	flush := func() {
		if len(buf) > 0 {
			counts[string(buf)]++
			total++
			buf = buf[:0]
		}
	}

	for _, b := range data {
		switch {
		case b >= 'a' && b <= 'z':
			buf = append(buf, b)
		case b >= 'A' && b <= 'Z':
			buf = append(buf, b+('a'-'A'))
		default:
			flush()
		}
	}
	flush()

	type entry struct {
		word  string
		count int
	}
	entries := make([]entry, 0, len(counts))
	for w, c := range counts {
		entries = append(entries, entry{w, c})
	}
	sort.Slice(entries, func(i, j int) bool {
		if entries[i].count != entries[j].count {
			return entries[i].count > entries[j].count
		}
		return entries[i].word < entries[j].word
	})

	out := bufio.NewWriter(os.Stdout)
	defer out.Flush()

	fmt.Fprintf(out, "words %d unique %d\n", total, len(counts))
	limit := len(entries)
	if limit > 20 {
		limit = 20
	}
	for i := 0; i < limit; i++ {
		fmt.Fprintf(out, "%s %d\n", entries[i].word, entries[i].count)
	}
}
