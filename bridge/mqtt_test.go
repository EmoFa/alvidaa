package main

import (
	"bufio"
	"context"
	"fmt"
	"net"
	"sync"
	"testing"
	"time"
)

// fakeBroker speaks just enough MQTT to exercise the client.
type fakeBroker struct {
	ln      net.Listener
	connack byte

	mu        sync.Mutex
	subs      []string
	published map[string][]byte
	connected chan struct{}
	conn      net.Conn
}

func newFakeBroker(t *testing.T, connack byte) *fakeBroker {
	t.Helper()
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	b := &fakeBroker{ln: ln, connack: connack, published: map[string][]byte{}, connected: make(chan struct{})}
	go b.serve()
	return b
}

func (b *fakeBroker) serve() {
	conn, err := b.ln.Accept()
	if err != nil {
		return
	}
	b.mu.Lock()
	b.conn = conn
	b.mu.Unlock()
	br := bufio.NewReader(conn)
	h, _, err := readPacket(br)
	if err != nil || h>>4 != 1 {
		conn.Close()
		return
	}
	conn.Write([]byte{0x20, 0x02, 0x00, b.connack})
	if b.connack != 0 {
		conn.Close()
		return
	}
	close(b.connected)
	for {
		h, p, err := readPacket(br)
		if err != nil {
			return
		}
		switch h >> 4 {
		case 8: // SUBSCRIBE
			id := uint16(p[0])<<8 | uint16(p[1])
			// parse topic filters
			rest := p[2:]
			var got []string
			for len(rest) >= 2 {
				n := int(rest[0])<<8 | int(rest[1])
				if len(rest) < 2+n+1 {
					break
				}
				got = append(got, string(rest[2:2+n]))
				rest = rest[2+n+1:]
			}
			b.mu.Lock()
			b.subs = append(b.subs, got...)
			b.mu.Unlock()
			conn.Write([]byte{0x90, 0x03, byte(id >> 8), byte(id), 0x00})
		case 3: // PUBLISH
			topic, payload, err := parsePublish(h, p)
			if err != nil {
				return
			}
			b.mu.Lock()
			b.published[topic] = payload
			b.mu.Unlock()
		case 12: // PINGREQ
			conn.Write([]byte{0xD0, 0x00})
		}
	}
}

func (b *fakeBroker) publish(topic string, payload string) {
	b.mu.Lock()
	conn := b.conn
	b.mu.Unlock()
	conn.Write(publishPacket(topic, []byte(payload)))
}

func (b *fakeBroker) subscriptions() []string {
	b.mu.Lock()
	defer b.mu.Unlock()
	return append([]string(nil), b.subs...)
}

func (b *fakeBroker) last(topic string) ([]byte, bool) {
	b.mu.Lock()
	defer b.mu.Unlock()
	v, ok := b.published[topic]
	return v, ok
}

func (b *fakeBroker) close() {
	b.mu.Lock()
	if b.conn != nil {
		b.conn.Close()
	}
	b.mu.Unlock()
	b.ln.Close()
}

func TestClientConnectsSubscribesAndPublishes(t *testing.T) {
	broker := newFakeBroker(t, 0)
	defer broker.close()

	client := NewClient(broker.ln.Addr().String(), nil, "dev-1", "user", "pass")
	messages := make(chan string, 4)
	connected := make(chan struct{}, 1)
	client.OnConnect = func(c *Client) {
		connected <- struct{}{}
		if err := c.Subscribe([]string{"/a/b", "/c/d"}); err != nil {
			t.Errorf("subscribe: %v", err)
		}
	}
	client.OnMessage = func(topic string, payload []byte) {
		messages <- topic + "=" + string(payload)
	}

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	go client.Run(ctx)

	select {
	case <-connected:
	case <-time.After(5 * time.Second):
		t.Fatal("client never connected")
	}
	time.Sleep(100 * time.Millisecond) // let SUBSCRIBE reach the broker

	if got := broker.subscriptions(); len(got) != 2 || got[0] != "/a/b" || got[1] != "/c/d" {
		t.Fatalf("subscriptions = %v", got)
	}

	if err := client.Publish("/remoteapp/tv/ui_service/dev-1/actions/gettvstate", nil); err != nil {
		t.Fatalf("publish: %v", err)
	}
	time.Sleep(100 * time.Millisecond)
	if _, ok := broker.last("/remoteapp/tv/ui_service/dev-1/actions/gettvstate"); !ok {
		t.Fatal("broker never saw the publish")
	}

	broker.publish("/remoteapp/mobile/dev-1/ui_service/data/applist", `[{"name":"Netflix"}]`)
	select {
	case got := <-messages:
		if got != `/remoteapp/mobile/dev-1/ui_service/data/applist=[{"name":"Netflix"}]` {
			t.Fatalf("message = %s", got)
		}
	case <-time.After(3 * time.Second):
		t.Fatal("no message delivered")
	}

	if !client.Connected() {
		t.Fatal("client should report connected")
	}
}

func TestClientRejectedInvokesRefresh(t *testing.T) {
	broker := newFakeBroker(t, 5) // not authorised
	defer broker.close()

	client := NewClient(broker.ln.Addr().String(), nil, "dev-1", "user", "pass")
	rejected := make(chan byte, 1)
	client.OnReject = func(rc byte) bool {
		rejected <- rc
		return false
	}
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	go client.Run(ctx)

	select {
	case rc := <-rejected:
		if rc != 5 {
			t.Fatalf("rc = %d", rc)
		}
	case <-time.After(5 * time.Second):
		t.Fatal("OnReject never called")
	}
	if client.Connected() {
		t.Fatal("client must not report connected after a rejection")
	}
}

func TestAskMatchesReplyShape(t *testing.T) {
	// Exercise the inbox matching logic without a broker: call() would fail,
	// so feed the queue directly through onMessage.
	b := &Bridge{inbox: make(chan inboxMsg, 8)}
	b.onMessage("/remoteapp/mobile/x/ui_service/data/applist", []byte(`[{"name":"A"}]`))
	b.onMessage("/remoteapp/mobile/x/ui_service/data/state", []byte(`{"statetype":"remote_launcher"}`))

	v, err := waitFor(&b.inbox, true, time.Second)
	if err != nil {
		t.Fatal(err)
	}
	if list := toMapList(v); len(list) != 1 || list[0]["name"] != "A" {
		t.Fatalf("list = %v", v)
	}
}

// waitFor mirrors ask's matching without publishing.
func waitFor(inbox *chan inboxMsg, isList bool, timeout time.Duration) (any, error) {
	deadline := time.After(timeout)
	for {
		select {
		case m := <-*inbox:
			_, slice := m.payload.([]any)
			if slice == isList {
				return m.payload, nil
			}
		case <-deadline:
			return nil, fmt.Errorf("timeout")
		}
	}
}
