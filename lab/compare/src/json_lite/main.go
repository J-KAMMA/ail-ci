package main

import (
	"fmt"
	"io"
	"os"
	"strconv"
)

type parser struct {
	data  []byte
	i     int
	total int64
}

func (p *parser) skipWS() {
	for p.i < len(p.data) {
		c := p.data[p.i]
		if c == ' ' || c == '\t' || c == '\r' || c == '\n' {
			p.i++
		} else {
			break
		}
	}
}

func (p *parser) skipString() {
	p.i++
	for p.i < len(p.data) {
		if p.data[p.i] == '\\' {
			p.i += 2
		} else if p.data[p.i] == '"' {
			p.i++
			return
		} else {
			p.i++
		}
	}
}

func (p *parser) parseValue() {
	p.skipWS()
	if p.i >= len(p.data) {
		return
	}
	c := p.data[p.i]
	if c == '{' {
		p.i++
		p.skipWS()
		if p.i < len(p.data) && p.data[p.i] == '}' {
			p.i++
			return
		}
		for {
			p.skipWS()
			if p.i >= len(p.data) {
				return
			}
			p.skipString()
			p.skipWS()
			if p.i < len(p.data) && p.data[p.i] == ':' {
				p.i++
			}
			p.parseValue()
			p.skipWS()
			if p.i < len(p.data) && p.data[p.i] == ',' {
				p.i++
				continue
			}
			if p.i < len(p.data) && p.data[p.i] == '}' {
				p.i++
			}
			return
		}
	}
	if c == '[' {
		p.i++
		p.skipWS()
		if p.i < len(p.data) && p.data[p.i] == ']' {
			p.i++
			return
		}
		for {
			p.skipWS()
			if p.i < len(p.data) && p.data[p.i] == ']' {
				p.i++
				return
			}
			if p.i >= len(p.data) {
				return
			}
			p.parseValue()
			p.skipWS()
			if p.i < len(p.data) && p.data[p.i] == ',' {
				p.i++
				continue
			}
			if p.i < len(p.data) && p.data[p.i] == ']' {
				p.i++
			}
			return
		}
	}
	if c == '"' {
		p.skipString()
		return
	}
	if c == '-' || (c >= '0' && c <= '9') {
		start := p.i
		if p.data[p.i] == '-' {
			p.i++
		}
		for p.i < len(p.data) && p.data[p.i] >= '0' && p.data[p.i] <= '9' {
			p.i++
		}
		value, _ := strconv.ParseInt(string(p.data[start:p.i]), 10, 64)
		p.total += value
		return
	}
	for _, word := range []string{"true", "false", "null"} {
		if p.i+len(word) <= len(p.data) && string(p.data[p.i:p.i+len(word)]) == word {
			p.i += len(word)
			return
		}
	}
	p.i++
}

func main() {
	data, _ := io.ReadAll(os.Stdin)
	p := &parser{data: data}
	for p.i < len(p.data) {
		p.parseValue()
		p.skipWS()
		if p.i >= len(p.data) {
			break
		}
	}
	fmt.Printf("%d\n", p.total)
}
