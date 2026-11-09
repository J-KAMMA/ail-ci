package main

import (
	"bufio"
	"fmt"
	"io"
	"os"
	"strings"
	"unicode/utf8"
)

func main() {
	levels := []string{"TRACE", "DEBUG", "INFO", "WARN", "ERROR", "FATAL"}
	index := make(map[string]int, len(levels))
	for i, l := range levels {
		index[l] = i
	}

	count := make([]int64, len(levels))
	chars := make([]int64, len(levels))
	longest := make([]int64, len(levels))
	var good, bad int64

	data, _ := io.ReadAll(os.Stdin)
	lines := strings.Split(string(data), "\n")

	for _, raw := range lines {
		line := strings.TrimSuffix(raw, "\r")
		if line == "" {
			continue
		}
		if line[0] != '[' {
			bad++
			continue
		}
		idx := strings.IndexByte(line, ']')
		if idx < 0 {
			bad++
			continue
		}
		pos, ok := index[line[1:idx]]
		if !ok {
			bad++
			continue
		}
		rest := line[idx+1:]
		msg := ""
		if rest != "" {
			if rest[0] != ' ' {
				bad++
				continue
			}
			msg = rest[1:]
		}
		good++
		n := int64(utf8.RuneCountInString(msg))
		count[pos]++
		chars[pos] += n
		if n > longest[pos] {
			longest[pos] = n
		}
	}

	w := bufio.NewWriter(os.Stdout)
	defer w.Flush()

	fmt.Fprintf(w, "lines %d bad %d\n", good, bad)
	for i, l := range levels {
		fmt.Fprintf(w, "level %s count %d chars %d longest %d\n", l, count[i], chars[i], longest[i])
	}
}
