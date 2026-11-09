package main

import (
	"bufio"
	"fmt"
	"io"
	"os"
	"sort"
)

type entry struct {
	word  string
	count int
}

func main() {
	data, err := io.ReadAll(os.Stdin)
	if err != nil {
		os.Exit(1)
	}

	counts := make(map[string]int)
	total := 0
	start := -1
	for i := 0; i <= len(data); i++ {
		isLetter := false
		if i < len(data) {
			c := data[i]
			isLetter = (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z')
		}
		if isLetter {
			if start < 0 {
				start = i
			}
			continue
		}
		if start >= 0 {
			b := make([]byte, i-start)
			for j := start; j < i; j++ {
				c := data[j]
				if c >= 'A' && c <= 'Z' {
					c += 'a' - 'A'
				}
				b[j-start] = c
			}
			counts[string(b)]++
			total++
			start = -1
		}
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
