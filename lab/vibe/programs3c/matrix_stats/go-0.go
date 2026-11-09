package main

import (
	"bufio"
	"fmt"
	"io"
	"os"
	"strconv"
	"strings"
)

func fail() {
	os.Stdout.WriteString("error\n")
	os.Exit(2)
}

func isSep(c byte) bool {
	return c == ' ' || c == '\t' || c == '\r' || c == '\v' || c == '\f'
}

func tokens(s string) []string {
	var out []string
	i, n := 0, len(s)
	for i < n {
		for i < n && isSep(s[i]) {
			i++
		}
		if i >= n {
			break
		}
		j := i
		for j < n && !isSep(s[j]) {
			j++
		}
		out = append(out, s[i:j])
		i = j
	}
	return out
}

func isDigits(s string) bool {
	if len(s) == 0 {
		return false
	}
	for i := 0; i < len(s); i++ {
		if s[i] < '0' || s[i] > '9' {
			return false
		}
	}
	return true
}

func main() {
	data, err := io.ReadAll(os.Stdin)
	if err != nil {
		fail()
	}
	text := string(data)
	var header, rest string
	if idx := strings.IndexByte(text, '\n'); idx >= 0 {
		header = text[:idx]
		rest = text[idx+1:]
	} else {
		header = text
	}

	ht := tokens(header)
	if len(ht) != 2 || !isDigits(ht[0]) || !isDigits(ht[1]) {
		fail()
	}
	R64, e1 := strconv.ParseInt(ht[0], 10, 64)
	C64, e2 := strconv.ParseInt(ht[1], 10, 64)
	if e1 != nil || e2 != nil {
		fail()
	}
	if R64 > 10000 || C64 > 10000 || R64*C64 > 1000000 {
		fail()
	}
	R, C := int(R64), int(C64)

	var lines []string
	if rest != "" {
		lines = strings.Split(rest, "\n")
		if lines[len(lines)-1] == "" {
			lines = lines[:len(lines)-1]
		}
	}
	if len(lines) < R {
		fail()
	}
	for _, extra := range lines[R:] {
		if len(tokens(extra)) != 0 {
			fail()
		}
	}

	rowSums := make([]int64, R)
	colSums := make([]int64, C)
	var maxVal int64
	found := false
	mr, mc := 0, 0

	for i := 0; i < R; i++ {
		toks := tokens(lines[i])
		if len(toks) != C {
			fail()
		}
		var s int64
		for j, t := range toks {
			v, e := strconv.ParseInt(t, 10, 64)
			if e != nil {
				fail()
			}
			s += v
			colSums[j] += v
			if !found || v > maxVal {
				maxVal = v
				mr, mc = i, j
				found = true
			}
		}
		rowSums[i] = s
	}

	w := bufio.NewWriter(os.Stdout)
	for i := 0; i < R; i++ {
		fmt.Fprintf(w, "row %d %d\n", i, rowSums[i])
	}
	for j := 0; j < C; j++ {
		fmt.Fprintf(w, "col %d %d\n", j, colSums[j])
	}
	if !found {
		fmt.Fprintf(w, "max none\n")
	} else {
		fmt.Fprintf(w, "max %d at %d %d\n", maxVal, mr, mc)
	}
	w.Flush()
}
