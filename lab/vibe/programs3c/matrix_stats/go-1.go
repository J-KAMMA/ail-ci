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

func isDigits(s string) bool {
	if s == "" {
		return false
	}
	for i := 0; i < len(s); i++ {
		if s[i] < '0' || s[i] > '9' {
			return false
		}
	}
	return true
}

func parseDim(s string) (int64, bool) {
	if !isDigits(s) {
		return 0, false
	}
	v, err := strconv.ParseInt(s, 10, 64)
	if err != nil {
		return 0, false
	}
	return v, true
}

func main() {
	data, err := io.ReadAll(os.Stdin)
	if err != nil {
		fail()
	}
	text := string(data)
	lines := strings.Split(text, "\n")
	if len(lines) > 0 && lines[len(lines)-1] == "" {
		lines = lines[:len(lines)-1]
	}
	if len(lines) == 0 {
		fail()
	}

	hdr := strings.Fields(lines[0])
	if len(hdr) != 2 {
		fail()
	}
	r64, ok1 := parseDim(hdr[0])
	c64, ok2 := parseDim(hdr[1])
	if !ok1 || !ok2 {
		fail()
	}
	if r64 < 0 || r64 > 10000 || c64 < 0 || c64 > 10000 {
		fail()
	}
	if r64*c64 > 1000000 {
		fail()
	}
	R := int(r64)
	C := int(c64)

	if len(lines)-1 < R {
		fail()
	}
	for k := 1 + R; k < len(lines); k++ {
		if len(strings.Fields(lines[k])) > 0 {
			fail()
		}
	}

	vals := make([]int64, R*C)
	for i := 0; i < R; i++ {
		f := strings.Fields(lines[1+i])
		if len(f) != C {
			fail()
		}
		for j := 0; j < C; j++ {
			v, err := strconv.ParseInt(f[j], 10, 64)
			if err != nil {
				fail()
			}
			vals[i*C+j] = v
		}
	}

	w := bufio.NewWriter(os.Stdout)
	defer w.Flush()

	for i := 0; i < R; i++ {
		var s int64
		for j := 0; j < C; j++ {
			s += vals[i*C+j]
		}
		fmt.Fprintf(w, "row %d %d\n", i, s)
	}

	for j := 0; j < C; j++ {
		var s int64
		for i := 0; i < R; i++ {
			s += vals[i*C+j]
		}
		fmt.Fprintf(w, "col %d %d\n", j, s)
	}

	if R*C == 0 {
		fmt.Fprintf(w, "max none\n")
		return
	}

	maxV := vals[0]
	mr, mc := 0, 0
	for i := 0; i < R; i++ {
		for j := 0; j < C; j++ {
			v := vals[i*C+j]
			if v > maxV {
				maxV = v
				mr = i
				mc = j
			}
		}
	}
	fmt.Fprintf(w, "max %d at %d %d\n", maxV, mr, mc)
}
