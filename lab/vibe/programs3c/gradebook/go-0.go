package main

import (
	"bufio"
	"fmt"
	"io"
	"os"
	"sort"
	"strings"
)

type stat struct {
	name  string
	count int64
	sum   int64
}

// parseScore parses an ASCII decimal integer in 0..10^12 (leading zeros allowed).
func parseScore(s string) (int64, bool) {
	if len(s) == 0 {
		return 0, false
	}
	const limit int64 = 1000000000000
	var v int64
	for i := 0; i < len(s); i++ {
		c := s[i]
		if c < '0' || c > '9' {
			return 0, false
		}
		v = v*10 + int64(c-'0')
		if v > limit {
			return 0, false
		}
	}
	return v, true
}

func main() {
	reader := bufio.NewReaderSize(os.Stdin, 1<<16)
	writer := bufio.NewWriter(os.Stdout)
	defer writer.Flush()

	stats := make(map[string]*stat)
	var bad int64

	for {
		line, err := reader.ReadString('\n')
		if len(line) > 0 {
			fields := strings.Fields(line)
			if len(fields) == 0 {
				// blank line: skipped, not bad
			} else if len(fields) != 3 {
				bad++
			} else {
				score, ok := parseScore(fields[2])
				if !ok {
					bad++
				} else {
					name := fields[0]
					st, exists := stats[name]
					if !exists {
						st = &stat{name: name}
						stats[name] = st
					}
					st.count++
					st.sum += score
				}
			}
		}
		if err != nil {
			if err != io.EOF {
				// treat read errors as end of input
			}
			break
		}
	}

	list := make([]*stat, 0, len(stats))
	for _, st := range stats {
		list = append(list, st)
	}

	sort.Slice(list, func(i, j int) bool {
		ai := list[i].sum / list[i].count
		aj := list[j].sum / list[j].count
		if ai != aj {
			return ai > aj
		}
		return list[i].name < list[j].name
	})

	fmt.Fprintf(writer, "bad %d\n", bad)
	for _, st := range list {
		avg := st.sum / st.count
		fmt.Fprintf(writer, "%s count %d sum %d avg %d\n", st.name, st.count, st.sum, avg)
	}
}
