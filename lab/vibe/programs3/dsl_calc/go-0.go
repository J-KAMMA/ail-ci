package main

import (
	"bufio"
	"fmt"
	"io"
	"math/big"
	"os"
	"strconv"
	"strings"
)

func parseInt64(s string) (int64, bool) {
	if s == "" {
		return 0, false
	}
	start := 0
	if s[0] == '-' {
		start = 1
		if len(s) == 1 {
			return 0, false
		}
	}
	for i := start; i < len(s); i++ {
		if s[i] < '0' || s[i] > '9' {
			return 0, false
		}
	}
	v, err := strconv.ParseInt(s, 10, 64)
	if err != nil {
		return 0, false
	}
	return v, true
}

func calc(op string, a, b int64) (int64, bool) {
	x := big.NewInt(a)
	y := big.NewInt(b)
	z := new(big.Int)
	switch op {
	case "add":
		z.Add(x, y)
	case "sub":
		z.Sub(x, y)
	case "mul":
		z.Mul(x, y)
	}
	if !z.IsInt64() {
		return 0, false
	}
	return z.Int64(), true
}

func main() {
	data, _ := io.ReadAll(os.Stdin)
	lines := strings.Split(string(data), "\n")

	var stack []int64
	vars := make(map[string]int64)

	out := bufio.NewWriter(os.Stdout)
	defer out.Flush()

	for idx, raw := range lines {
		lineNo := idx + 1
		raw = strings.TrimSuffix(raw, "\r")
		line := strings.Trim(raw, " \t")
		if line == "" || line[0] == '#' {
			continue
		}

		fields := strings.Fields(line)
		cmd := fields[0]
		args := fields[1:]
		reason := ""

		switch cmd {
		case "push":
			if len(args) != 1 {
				reason = "cmd"
				break
			}
			v, ok := parseInt64(args[0])
			if !ok {
				reason = "int"
				break
			}
			stack = append(stack, v)

		case "add", "sub", "mul":
			if len(args) != 0 {
				reason = "cmd"
				break
			}
			if len(stack) < 2 {
				reason = "stack"
				break
			}
			a := stack[len(stack)-2]
			b := stack[len(stack)-1]
			r, ok := calc(cmd, a, b)
			if !ok {
				reason = "overflow"
				break
			}
			stack = stack[:len(stack)-2]
			stack = append(stack, r)

		case "dup":
			if len(args) != 0 {
				reason = "cmd"
				break
			}
			if len(stack) < 1 {
				reason = "stack"
				break
			}
			stack = append(stack, stack[len(stack)-1])

		case "swap":
			if len(args) != 0 {
				reason = "cmd"
				break
			}
			if len(stack) < 2 {
				reason = "stack"
				break
			}
			n := len(stack)
			stack[n-1], stack[n-2] = stack[n-2], stack[n-1]

		case "drop":
			if len(args) != 0 {
				reason = "cmd"
				break
			}
			if len(stack) < 1 {
				reason = "stack"
				break
			}
			stack = stack[:len(stack)-1]

		case "store":
			if len(args) != 1 {
				reason = "cmd"
				break
			}
			if len(stack) < 1 {
				reason = "stack"
				break
			}
			v := stack[len(stack)-1]
			stack = stack[:len(stack)-1]
			vars[args[0]] = v

		case "load":
			if len(args) != 1 {
				reason = "cmd"
				break
			}
			v, ok := vars[args[0]]
			if !ok {
				reason = "var"
				break
			}
			stack = append(stack, v)

		case "print":
			if len(args) != 0 {
				reason = "cmd"
				break
			}
			if len(stack) < 1 {
				reason = "stack"
				break
			}
			fmt.Fprintf(out, "value %d\n", stack[len(stack)-1])

		case "clear":
			if len(args) != 0 {
				reason = "cmd"
				break
			}
			stack = stack[:0]

		default:
			reason = "cmd"
		}

		if reason != "" {
			fmt.Fprintf(out, "error %d %s\n", lineNo, reason)
		}
	}

	fmt.Fprintf(out, "stack %d\n", len(stack))
	if len(stack) > 0 {
		for i, v := range stack {
			if i > 0 {
				out.WriteByte(' ')
			}
			out.WriteString(strconv.FormatInt(v, 10))
		}
		out.WriteByte('\n')
	}
}
