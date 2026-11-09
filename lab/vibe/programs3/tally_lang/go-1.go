package main

import (
	"bufio"
	"fmt"
	"math/bits"
	"os"
	"strconv"
	"strings"
)

const (
	tokNum = iota
	tokWord
	tokOp
)

const (
	eNum = iota
	eVar
	eBin
	eUn
)

const (
	stSet = iota
	stOut
	stLoop
	stWhen
	stBreak
	stElse
	stEnd
)

type token struct {
	kind int
	text string
	num  uint32
}

type exprNode struct {
	kind        int
	num         uint32
	name        string
	op          string
	left, right *exprNode
}

type stmtNode struct {
	kind     int
	line     int
	name     string
	exprs    []*exprNode
	body     []*stmtNode
	elseBody []*stmtNode
}

type stmtFrame struct {
	s      *stmtNode
	inElse bool
}

type parseErr struct{ line int }

func splitLines(data []byte) [][]byte {
	var lines [][]byte
	start := 0
	for i := 0; i < len(data); i++ {
		if data[i] == '\n' {
			lines = append(lines, data[start:i])
			start = i + 1
		}
	}
	if start < len(data) {
		lines = append(lines, data[start:])
	}
	return lines
}

func isKeyword(s string) bool {
	switch s {
	case "set", "out", "loop", "when", "else", "end", "break":
		return true
	}
	return false
}

func isCmp(s string) bool {
	return s == "==" || s == "!=" || s == "<" || s == ">"
}

func tokenize(line []byte) ([]token, bool) {
	var toks []token
	i, n := 0, len(line)
	for i < n {
		c := line[i]
		if c == ' ' || c == '\t' || c == '\r' {
			i++
			continue
		}
		if c >= '0' && c <= '9' {
			var val uint64
			j := i
			for j < n && line[j] >= '0' && line[j] <= '9' {
				val = val*10 + uint64(line[j]-'0')
				if val > 4294967295 {
					return nil, false
				}
				j++
			}
			if j < n {
				nc := line[j]
				if (nc >= 'a' && nc <= 'z') || nc == '_' {
					return nil, false
				}
			}
			toks = append(toks, token{kind: tokNum, num: uint32(val)})
			i = j
			continue
		}
		if (c >= 'a' && c <= 'z') || c == '_' {
			j := i + 1
			for j < n {
				cc := line[j]
				if (cc >= 'a' && cc <= 'z') || (cc >= '0' && cc <= '9') || cc == '_' {
					j++
				} else {
					break
				}
			}
			toks = append(toks, token{kind: tokWord, text: string(line[i:j])})
			i = j
			continue
		}
		if i+1 < n {
			two := string(line[i : i+2])
			if two == "<>" || two == "><" || two == "==" || two == "!=" {
				toks = append(toks, token{kind: tokOp, text: two})
				i += 2
				continue
			}
		}
		if strings.IndexByte("<>+-*/%~#!(),=", c) >= 0 {
			toks = append(toks, token{kind: tokOp, text: string(c)})
			i++
			continue
		}
		return nil, false
	}
	return toks, true
}

type exprParser struct {
	toks  []token
	pos   int
	depth int
}

func (p *exprParser) peek() (token, bool) {
	if p.pos < len(p.toks) {
		return p.toks[p.pos], true
	}
	return token{}, false
}

func (p *exprParser) parseFull() (*exprNode, bool) {
	p.depth = 0
	return p.parseL1()
}

func (p *exprParser) parseL1() (*exprNode, bool) {
	left, ok := p.parseL2()
	if !ok {
		return nil, false
	}
	for {
		t, has := p.peek()
		if !has || t.kind != tokOp || (t.text != "<>" && t.text != "><") {
			break
		}
		p.pos++
		right, ok := p.parseL2()
		if !ok {
			return nil, false
		}
		left = &exprNode{kind: eBin, op: t.text, left: left, right: right}
	}
	return left, true
}

func (p *exprParser) parseL2() (*exprNode, bool) {
	left, ok := p.parseL3()
	if !ok {
		return nil, false
	}
	t, has := p.peek()
	if has && t.kind == tokOp && isCmp(t.text) {
		p.pos++
		right, ok := p.parseL3()
		if !ok {
			return nil, false
		}
		left = &exprNode{kind: eBin, op: t.text, left: left, right: right}
		if t2, has2 := p.peek(); has2 && t2.kind == tokOp && isCmp(t2.text) {
			return nil, false
		}
	}
	return left, true
}

func (p *exprParser) parseL3() (*exprNode, bool) {
	left, ok := p.parseL4()
	if !ok {
		return nil, false
	}
	for {
		t, has := p.peek()
		if !has || t.kind != tokOp || (t.text != "+" && t.text != "-") {
			break
		}
		p.pos++
		right, ok := p.parseL4()
		if !ok {
			return nil, false
		}
		left = &exprNode{kind: eBin, op: t.text, left: left, right: right}
	}
	return left, true
}

func (p *exprParser) parseL4() (*exprNode, bool) {
	left, ok := p.parseL5()
	if !ok {
		return nil, false
	}
	for {
		t, has := p.peek()
		if !has || t.kind != tokOp || (t.text != "*" && t.text != "/" && t.text != "%") {
			break
		}
		p.pos++
		right, ok := p.parseL5()
		if !ok {
			return nil, false
		}
		left = &exprNode{kind: eBin, op: t.text, left: left, right: right}
	}
	return left, true
}

func (p *exprParser) parseL5() (*exprNode, bool) {
	left, ok := p.parseL6()
	if !ok {
		return nil, false
	}
	t, has := p.peek()
	if has && t.kind == tokOp && t.text == "~" {
		p.pos++
		right, ok := p.parseL5()
		if !ok {
			return nil, false
		}
		return &exprNode{kind: eBin, op: "~", left: left, right: right}, true
	}
	return left, true
}

func (p *exprParser) parseL6() (*exprNode, bool) {
	t, has := p.peek()
	if has && t.kind == tokOp && (t.text == "-" || t.text == "#" || t.text == "!") {
		p.pos++
		operand, ok := p.parseL6()
		if !ok {
			return nil, false
		}
		return &exprNode{kind: eUn, op: t.text, left: operand}, true
	}
	return p.parseL7()
}

func (p *exprParser) parseL7() (*exprNode, bool) {
	t, has := p.peek()
	if !has {
		return nil, false
	}
	if t.kind == tokNum {
		p.pos++
		return &exprNode{kind: eNum, num: t.num}, true
	}
	if t.kind == tokWord {
		if isKeyword(t.text) {
			return nil, false
		}
		p.pos++
		return &exprNode{kind: eVar, name: t.text}, true
	}
	if t.kind == tokOp && t.text == "(" {
		p.depth++
		if p.depth > 32 {
			return nil, false
		}
		p.pos++
		e, ok := p.parseL1()
		if !ok {
			return nil, false
		}
		t2, has2 := p.peek()
		if !has2 || t2.kind != tokOp || t2.text != ")" {
			return nil, false
		}
		p.pos++
		p.depth--
		return e, true
	}
	return nil, false
}

func parseLine(toks []token, line int) (int, *stmtNode, bool) {
	p := &exprParser{toks: toks}
	first, _ := p.peek()
	if first.kind != tokWord {
		return 0, nil, false
	}
	switch first.text {
	case "set":
		p.pos++
		nt, ok := p.peek()
		if !ok || nt.kind != tokWord || isKeyword(nt.text) {
			return 0, nil, false
		}
		p.pos++
		et, ok := p.peek()
		if !ok || et.kind != tokOp || et.text != "=" {
			return 0, nil, false
		}
		p.pos++
		e, ok := p.parseFull()
		if !ok || p.pos != len(p.toks) {
			return 0, nil, false
		}
		return stSet, &stmtNode{kind: stSet, line: line, name: nt.text, exprs: []*exprNode{e}}, true
	case "out":
		p.pos++
		if p.pos >= len(p.toks) {
			return 0, nil, false
		}
		var es []*exprNode
		for {
			e, ok := p.parseFull()
			if !ok {
				return 0, nil, false
			}
			es = append(es, e)
			t, ok := p.peek()
			if ok && t.kind == tokOp && t.text == "," {
				p.pos++
				continue
			}
			break
		}
		if p.pos != len(p.toks) {
			return 0, nil, false
		}
		return stOut, &stmtNode{kind: stOut, line: line, exprs: es}, true
	case "loop", "when":
		p.pos++
		e, ok := p.parseFull()
		if !ok || p.pos != len(p.toks) {
			return 0, nil, false
		}
		k := stLoop
		if first.text == "when" {
			k = stWhen
		}
		return k, &stmtNode{kind: k, line: line, exprs: []*exprNode{e}}, true
	case "else":
		p.pos++
		if p.pos != len(p.toks) {
			return 0, nil, false
		}
		return stElse, &stmtNode{line: line}, true
	case "end":
		p.pos++
		if p.pos != len(p.toks) {
			return 0, nil, false
		}
		return stEnd, &stmtNode{line: line}, true
	case "break":
		p.pos++
		if p.pos != len(p.toks) {
			return 0, nil, false
		}
		return stBreak, &stmtNode{kind: stBreak, line: line}, true
	}
	return 0, nil, false
}

func parseProgram(lines [][]byte) ([]*stmtNode, *parseErr) {
	var top []*stmtNode
	var stack []*stmtFrame

	appendStmt := func(s *stmtNode) {
		if len(stack) == 0 {
			top = append(top, s)
		} else {
			f := stack[len(stack)-1]
			if f.inElse {
				f.s.elseBody = append(f.s.elseBody, s)
			} else {
				f.s.body = append(f.s.body, s)
			}
		}
	}

	for idx, raw := range lines {
		lineNo := idx + 1

		valid := true
		for _, c := range raw {
			if c == '\t' || c == '\r' {
				continue
			}
			if c < 0x20 || c > 0x7E {
				valid = false
				break
			}
		}
		if !valid || len(raw) > 1000 {
			return nil, &parseErr{lineNo}
		}

		line := raw
		for i := 0; i < len(line); i++ {
			if line[i] == ';' {
				line = line[:i]
				break
			}
		}

		toks, ok := tokenize(line)
		if !ok {
			return nil, &parseErr{lineNo}
		}
		if len(toks) == 0 {
			continue
		}

		kind, s, ok := parseLine(toks, lineNo)
		if !ok {
			return nil, &parseErr{lineNo}
		}

		switch kind {
		case stElse:
			if len(stack) == 0 {
				return nil, &parseErr{lineNo}
			}
			f := stack[len(stack)-1]
			if f.s.kind != stWhen || f.inElse {
				return nil, &parseErr{lineNo}
			}
			f.inElse = true
		case stEnd:
			if len(stack) == 0 {
				return nil, &parseErr{lineNo}
			}
			stack = stack[:len(stack)-1]
		case stBreak:
			inLoop := false
			for _, f := range stack {
				if f.s.kind == stLoop {
					inLoop = true
					break
				}
			}
			if !inLoop {
				return nil, &parseErr{lineNo}
			}
			appendStmt(s)
		case stLoop, stWhen:
			if len(stack) >= 16 {
				return nil, &parseErr{lineNo}
			}
			appendStmt(s)
			stack = append(stack, &stmtFrame{s: s})
		default:
			appendStmt(s)
		}
	}

	if len(stack) > 0 {
		return nil, &parseErr{stack[len(stack)-1].s.line}
	}
	return top, nil
}

func evalExpr(e *exprNode, vars map[string]uint32) (uint32, bool) {
	switch e.kind {
	case eNum:
		return e.num, true
	case eVar:
		v, ok := vars[e.name]
		if !ok {
			return 0, false
		}
		return v, true
	case eUn:
		v, ok := evalExpr(e.left, vars)
		if !ok {
			return 0, false
		}
		switch e.op {
		case "-":
			return 0 - v, true
		case "#":
			return uint32(bits.OnesCount32(v)), true
		case "!":
			if v == 0 {
				return 1, true
			}
			return 0, true
		}
	case eBin:
		l, ok := evalExpr(e.left, vars)
		if !ok {
			return 0, false
		}
		r, ok := evalExpr(e.right, vars)
		if !ok {
			return 0, false
		}
		switch e.op {
		case "<>":
			if l > r {
				return l, true
			}
			return r, true
		case "><":
			if l < r {
				return l, true
			}
			return r, true
		case "==":
			if l == r {
				return 1, true
			}
			return 0, true
		case "!=":
			if l != r {
				return 1, true
			}
			return 0, true
		case "<":
			if l < r {
				return 1, true
			}
			return 0, true
		case ">":
			if l > r {
				return 1, true
			}
			return 0, true
		case "+":
			return l + r, true
		case "-":
			return l - r, true
		case "*":
			return l * r, true
		case "/":
			if r == 0 {
				return 0, false
			}
			return l / r, true
		case "%":
			if r == 0 {
				return 0, false
			}
			return l % r, true
		case "~":
			n := r % 32
			if n == 0 {
				return l, true
			}
			return (l << n) | (l >> (32 - n)), true
		}
	}
	return 0, false
}

type runtimeErr struct{ line int }

func execList(list []*stmtNode, vars map[string]uint32, w *bufio.Writer) (bool, *runtimeErr) {
	for _, s := range list {
		brk, err := execStmt(s, vars, w)
		if err != nil {
			return false, err
		}
		if brk {
			return true, nil
		}
	}
	return false, nil
}

func execStmt(s *stmtNode, vars map[string]uint32, w *bufio.Writer) (bool, *runtimeErr) {
	switch s.kind {
	case stSet:
		v, ok := evalExpr(s.exprs[0], vars)
		if !ok {
			return false, &runtimeErr{s.line}
		}
		vars[s.name] = v
		return false, nil
	case stOut:
		vals := make([]uint32, len(s.exprs))
		for i, e := range s.exprs {
			v, ok := evalExpr(e, vars)
			if !ok {
				return false, &runtimeErr{s.line}
			}
			vals[i] = v
		}
		for i, v := range vals {
			if i > 0 {
				w.WriteByte(' ')
			}
			w.WriteString(strconv.FormatUint(uint64(v), 10))
		}
		w.WriteByte('\n')
		return false, nil
	case stLoop:
		v, ok := evalExpr(s.exprs[0], vars)
		if !ok {
			return false, &runtimeErr{s.line}
		}
		if len(s.body) == 0 {
			return false, nil
		}
		n := v
		for i := uint32(0); i < n; i++ {
			brk, err := execList(s.body, vars, w)
			if err != nil {
				return false, err
			}
			if brk {
				break
			}
		}
		return false, nil
	case stWhen:
		v, ok := evalExpr(s.exprs[0], vars)
		if !ok {
			return false, &runtimeErr{s.line}
		}
		if v != 0 {
			return execList(s.body, vars, w)
		}
		return execList(s.elseBody, vars, w)
	case stBreak:
		return true, nil
	}
	return false, nil
}

func main() {
	if len(os.Args) != 2 {
		os.Exit(1)
	}
	data, err := os.ReadFile(os.Args[1])
	if err != nil {
		os.Exit(1)
	}

	prog, perr := parseProgram(splitLines(data))

	w := bufio.NewWriter(os.Stdout)
	if perr != nil {
		fmt.Fprintf(w, "parse error line %d\n", perr.line)
		w.Flush()
		os.Exit(2)
	}

	vars := make(map[string]uint32)
	_, rerr := execList(prog, vars, w)
	if rerr != nil {
		w.Flush()
		fmt.Fprintf(w, "runtime error line %d\n", rerr.line)
		w.Flush()
		os.Exit(3)
	}

	w.Flush()
}
