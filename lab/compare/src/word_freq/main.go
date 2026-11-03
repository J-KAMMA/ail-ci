package main

import (
	"fmt"
	"io"
	"os"
	"sort"
)

type rankedWord struct {
	word  string
	count int64
}

func main() {
	data, _ := io.ReadAll(os.Stdin)
	counts := make(map[string]int64)
	word := make([]byte, 0, 64)
	for _, b := range data {
		if b >= 'A' && b <= 'Z' {
			word = append(word, b+32)
		} else if b >= 'a' && b <= 'z' {
			word = append(word, b)
		} else if len(word) > 0 {
			key := string(word)
			counts[key]++
			word = word[:0]
		}
	}
	if len(word) > 0 {
		counts[string(word)]++
	}
	ranked := make([]rankedWord, 0, len(counts))
	for word, count := range counts {
		ranked = append(ranked, rankedWord{word, count})
	}
	sort.Slice(ranked, func(i, j int) bool {
		if ranked[i].count != ranked[j].count {
			return ranked[i].count > ranked[j].count
		}
		return ranked[i].word < ranked[j].word
	})
	if len(ranked) > 20 {
		ranked = ranked[:20]
	}
	for _, item := range ranked {
		fmt.Printf("%d %s\n", item.count, item.word)
	}
}
