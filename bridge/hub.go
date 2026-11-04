package main

import (
	"encoding/json"
	"sync"
)

// Hub fans bridge events out to every open overlay connection.
type Hub struct {
	mu    sync.Mutex
	conns map[*WSConn]struct{}
}

func NewHub() *Hub { return &Hub{conns: map[*WSConn]struct{}{}} }

func (h *Hub) Add(c *WSConn) {
	if h == nil {
		return
	}
	h.mu.Lock()
	h.conns[c] = struct{}{}
	h.mu.Unlock()
}

func (h *Hub) Remove(c *WSConn) {
	if h == nil {
		return
	}
	h.mu.Lock()
	delete(h.conns, c)
	h.mu.Unlock()
}

func (h *Hub) Broadcast(v any) {
	if h == nil {
		return
	}
	b, err := json.Marshal(v)
	if err != nil {
		return
	}
	h.mu.Lock()
	defer h.mu.Unlock()
	for c := range h.conns {
		if err := c.SendText(b); err != nil {
			delete(h.conns, c)
			c.Close()
		}
	}
}

func (h *Hub) Count() int {
	if h == nil {
		return 0
	}
	h.mu.Lock()
	defer h.mu.Unlock()
	return len(h.conns)
}
