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
	data, _ := io.ReadAll(os.Stdin)

	counts := make(map[string]int)
	total := 0
	start := -1

	for i := 0; i <= len(data); i++ {
		letter := false
		if i < len(data) {
			b := data[i]
			letter = (b >= 'A' && b <= 'Z') || (b >= 'a' && b <= 'z')
		}

		if letter {
			if start < 0 {
				start = i
			}
		} else if start >= 0 {
			w := data[start:i]
			for j := 0; j < len(w); j++ {
				if w[j] >= 'A' && w[j] <= 'Z' {
					w[j] += 'a' - 'A'
				}
			}
			counts[string(w)]++
			total++
			start = -1
		}
	}

	entries := make([]entry, 0, len(counts))
	for word, count := range counts {
		entries = append(entries, entry{word: word, count: count})
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

	n := len(entries)
	if n > 20 {
		n = 20
	}
	for i := 0; i < n; i++ {
		fmt.Fprintf(out, "%s %d\n", entries[i].word, entries[i].count)
	}
}
