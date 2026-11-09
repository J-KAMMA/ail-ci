package main

import (
	"bufio"
	"fmt"
	"io"
	"os"
	"sort"
	"strings"
)

const maxScore = 1000000000000

type stat struct {
	name  string
	count int64
	sum   int64
	avg   int64
}

func parseScore(s string) (int64, bool) {
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
		if v > maxScore {
			return 0, false
		}
	}
	return v, true
}

func main() {
	reader := bufio.NewReaderSize(os.Stdin, 1<<16)
	writer := bufio.NewWriter(os.Stdout)
	defer writer.Flush()

	bad := 0
	stats := make(map[string]*stat)

	for {
		line, err := reader.ReadString('\n')
		if len(line) > 0 {
			fields := strings.Fields(line)
			if len(fields) != 0 {
				if len(fields) != 3 {
					bad++
				} else if score, ok := parseScore(fields[2]); !ok {
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
				// treat any other read error as end of input
			}
			break
		}
	}

	list := make([]*stat, 0, len(stats))
	for _, st := range stats {
		st.avg = st.sum / st.count
		list = append(list, st)
	}

	sort.Slice(list, func(i, j int) bool {
		if list[i].avg != list[j].avg {
			return list[i].avg > list[j].avg
		}
		return list[i].name < list[j].name
	})

	fmt.Fprintf(writer, "bad %d\n", bad)
	for _, st := range list {
		fmt.Fprintf(writer, "%s count %d sum %d avg %d\n", st.name, st.count, st.sum, st.avg)
	}
}
