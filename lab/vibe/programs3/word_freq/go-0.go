package main

import (
	"bufio"
	"fmt"
	"os"
	"sort"
)

func main() {
	counts := make(map[string]int)
	total := 0

	reader := bufio.NewReader(os.Stdin)
	buf := make([]byte, 0, 64)
	for {
		c, err := reader.ReadByte()
		if err != nil {
			if len(buf) > 0 {
				w := string(buf)
				counts[w]++
				total++
				buf = buf[:0]
			}
			break
		}
		if (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') {
			if c >= 'A' && c <= 'Z' {
				c += 'a' - 'A'
			}
			buf = append(buf, c)
		} else if len(buf) > 0 {
			w := string(buf)
			counts[w]++
			total++
			buf = buf[:0]
		}
	}

	type wordCount struct {
		word  string
		count int
	}
	list := make([]wordCount, 0, len(counts))
	for w, c := range counts {
		list = append(list, wordCount{w, c})
	}
	sort.Slice(list, func(i, j int) bool {
		if list[i].count != list[j].count {
			return list[i].count > list[j].count
		}
		return list[i].word < list[j].word
	})

	out := bufio.NewWriter(os.Stdout)
	defer out.Flush()
	fmt.Fprintf(out, "words %d unique %d\n", total, len(counts))
	if len(list) > 20 {
		list = list[:20]
	}
	for _, wc := range list {
		fmt.Fprintf(out, "%s %d\n", wc.word, wc.count)
	}
}
