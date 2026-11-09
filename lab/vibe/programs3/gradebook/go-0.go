package main

import (
	"bufio"
	"fmt"
	"os"
	"sort"
	"strings"
)

const maxScore int64 = 1000000000000

type student struct {
	count int64
	sum   int64
}

func parseScore(s string) (int64, bool) {
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
	in := bufio.NewReader(os.Stdin)
	students := make(map[string]*student)
	var bad int64

	for {
		line, err := in.ReadString('\n')

		if len(line) > 0 {
			fields := strings.Fields(line)

			if len(fields) == 3 {
				score, ok := parseScore(fields[2])
				if !ok {
					bad++
				} else {
					st := students[fields[0]]
					if st == nil {
						st = &student{}
						students[fields[0]] = st
					}
					st.count++
					st.sum += score
				}
			} else if len(fields) != 0 {
				bad++
			}
		}

		if err != nil {
			break
		}
	}

	names := make([]string, 0, len(students))
	for name := range students {
		names = append(names, name)
	}

	sort.Slice(names, func(i, j int) bool {
		si := students[names[i]]
		sj := students[names[j]]
		ai := si.sum / si.count
		aj := sj.sum / sj.count

		if ai != aj {
			return ai > aj
		}
		return names[i] < names[j]
	})

	out := bufio.NewWriter(os.Stdout)
	defer out.Flush()

	fmt.Fprintf(out, "bad %d\n", bad)

	for _, name := range names {
		st := students[name]
		fmt.Fprintf(out, "%s count %d sum %d avg %d\n",
			name, st.count, st.sum, st.sum/st.count)
	}
}
