package main

import (
	"bufio"
	"fmt"
	"io"
	"os"
	"sort"
	"strings"
)

type studentStats struct {
	count int64
	sum   int64
}

type outputRow struct {
	name  string
	count int64
	sum   int64
	avg   int64
}

func parseScore(s string) (int64, bool) {
	const maxScore int64 = 1000000000000

	if s == "" {
		return 0, false
	}

	var value int64
	for i := 0; i < len(s); i++ {
		c := s[i]
		if c < '0' || c > '9' {
			return 0, false
		}

		digit := int64(c - '0')
		if value > (maxScore-digit)/10 {
			return 0, false
		}

		value = value*10 + digit
	}

	return value, true
}

func main() {
	reader := bufio.NewReader(os.Stdin)
	writer := bufio.NewWriter(os.Stdout)
	defer writer.Flush()

	stats := make(map[string]*studentStats)
	var bad int64

	for {
		line, err := reader.ReadString('\n')

		if len(line) > 0 {
			fields := strings.Fields(line)

			switch {
			case len(fields) == 0:
			case len(fields) != 3:
				bad++
			default:
				score, ok := parseScore(fields[2])
				if !ok {
					bad++
				} else {
					name := fields[0]
					st := stats[name]
					if st == nil {
						st = &studentStats{}
						stats[name] = st
					}
					st.count++
					st.sum += score
				}
			}
		}

		if err != nil {
			if err == io.EOF {
				break
			}
			break
		}
	}

	rows := make([]outputRow, 0, len(stats))
	for name, st := range stats {
		rows = append(rows, outputRow{
			name:  name,
			count: st.count,
			sum:   st.sum,
			avg:   st.sum / st.count,
		})
	}

	sort.Slice(rows, func(i, j int) bool {
		if rows[i].avg != rows[j].avg {
			return rows[i].avg > rows[j].avg
		}
		return rows[i].name < rows[j].name
	})

	fmt.Fprintf(writer, "bad %d\n", bad)

	for _, row := range rows {
		fmt.Fprintf(writer, "%s count %d sum %d avg %d\n", row.name, row.count, row.sum, row.avg)
	}
}
