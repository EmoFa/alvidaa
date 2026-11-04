// MQTT 3.1.1 client — the subset the TV's RemoteNow broker needs.
//
// Deliberately dependency-free: CONNECT/SUBSCRIBE/PUBLISH (QoS 0)/PING only.
// The TV broker denies wildcard subscriptions, so every topic is exact.
package main

import (
	"bufio"
	"context"
	"crypto/tls"
	"encoding/binary"
	"fmt"
	"io"
	"log"
	"net"
	"sync"
	"sync/atomic"
	"time"
)

const mqttProtoLevel = 4

type Client struct {
	Addr      string
	TLS       *tls.Config
	ClientID  string
	KeepAlive time.Duration

	// OnConnect runs after a successful CONNACK: subscribe here.
	OnConnect func(*Client)
	OnMessage func(topic string, payload []byte)
	// OnReject runs on a non-zero CONNACK code. Return true when credentials
	// were refreshed and an immediate retry is worthwhile.
	OnReject func(rc byte) bool

	credMu   sync.RWMutex
	username string
	password string

	mu   sync.Mutex
	conn net.Conn
	id   atomic.Uint32
	up   atomic.Bool
}

func NewClient(addr string, tlsConf *tls.Config, clientID, user, pass string) *Client {
	c := &Client{Addr: addr, TLS: tlsConf, ClientID: clientID, KeepAlive: 30 * time.Second}
	c.SetCreds(user, pass)
	return c
}

func (c *Client) SetCreds(user, pass string) {
	c.credMu.Lock()
	c.username, c.password = user, pass
	c.credMu.Unlock()
}

func (c *Client) creds() (string, string) {
	c.credMu.RLock()
	defer c.credMu.RUnlock()
	return c.username, c.password
}

func (c *Client) Connected() bool { return c.up.Load() }

// Run keeps a session alive until ctx is cancelled.
func (c *Client) Run(ctx context.Context) {
	backoff := time.Second
	for ctx.Err() == nil {
		retryNow := c.once(ctx)
		if ctx.Err() != nil {
			return
		}
		if retryNow {
			backoff = time.Second
		}
		select {
		case <-ctx.Done():
			return
		case <-time.After(backoff):
		}
		if backoff < 30*time.Second {
			backoff *= 2
		}
		if backoff > 30*time.Second {
			backoff = 30 * time.Second
		}
	}
}

// once dials, connects and serves one session. It reports whether the caller
// should retry immediately (credentials were refreshed after a rejection).
func (c *Client) once(ctx context.Context) bool {
	d := net.Dialer{Timeout: 10 * time.Second}
	var (
		conn net.Conn
		err  error
	)
	if c.TLS != nil {
		conn, err = tls.DialWithDialer(&d, "tcp", c.Addr, c.TLS)
	} else {
		conn, err = d.DialContext(ctx, "tcp", c.Addr)
	}
	if err != nil {
		log.Printf("mqtt: dial %s: %v", c.Addr, err)
		return false
	}

	br := bufio.NewReader(conn)
	ka := c.KeepAlive
	if ka <= 0 {
		ka = 30 * time.Second
	}
	user, pass := c.creds()
	if _, err := conn.Write(connectPacket(c.ClientID, user, pass, uint16(ka.Seconds()))); err != nil {
		conn.Close()
		log.Printf("mqtt: write CONNECT: %v", err)
		return false
	}
	conn.SetReadDeadline(time.Now().Add(10 * time.Second))
	h, p, err := readPacket(br)
	conn.SetReadDeadline(time.Time{})
	if err != nil {
		conn.Close()
		log.Printf("mqtt: read CONNACK: %v", err)
		return false
	}
	if h>>4 != 2 || len(p) < 2 {
		conn.Close()
		log.Printf("mqtt: expected CONNACK, got type %d", h>>4)
		return false
	}
	if rc := p[1]; rc != 0 {
		conn.Close()
		log.Printf("mqtt: CONNACK rejected rc=%d", rc)
		if c.OnReject != nil && c.OnReject(rc) {
			return true // creds refreshed — retry at once
		}
		return false
	}

	c.mu.Lock()
	c.conn = conn
	c.mu.Unlock()
	c.up.Store(true)
	log.Printf("mqtt: connected to %s as %s", c.Addr, c.ClientID)

	pingCtx, stopPing := context.WithCancel(ctx)
	go c.pinger(pingCtx, ka)

	if c.OnConnect != nil {
		c.OnConnect(c)
	}

	err = c.readLoop(br)

	stopPing()
	c.up.Store(false)
	c.mu.Lock()
	c.conn = nil
	c.mu.Unlock()
	conn.Close()
	if err != nil && ctx.Err() == nil {
		log.Printf("mqtt: session ended: %v", err)
	}
	return false
}

func (c *Client) pinger(ctx context.Context, ka time.Duration) {
	t := time.NewTicker(ka / 2)
	defer t.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-t.C:
			if err := c.write([]byte{0xC0, 0x00}); err != nil {
				return
			}
		}
	}
}

func (c *Client) readLoop(br *bufio.Reader) error {
	for {
		h, p, err := readPacket(br)
		if err != nil {
			return err
		}
		switch h >> 4 {
		case 3: // PUBLISH
			topic, payload, err := parsePublish(h, p)
			if err != nil {
				return err
			}
			if c.OnMessage != nil {
				c.OnMessage(topic, payload)
			}
		case 9, 13: // SUBACK, PINGRESP — nothing to do
		case 14: // DISCONNECT from broker
			return fmt.Errorf("broker disconnected us")
		}
	}
}

func (c *Client) write(b []byte) error {
	c.mu.Lock()
	defer c.mu.Unlock()
	if c.conn == nil {
		return fmt.Errorf("not connected")
	}
	_, err := c.conn.Write(b)
	return err
}

func (c *Client) Publish(topic string, payload []byte) error {
	return c.write(publishPacket(topic, payload))
}

func (c *Client) Subscribe(topics []string) error {
	id := uint16(c.id.Add(1) & 0xFFFF)
	return c.write(subscribePacket(id, topics))
}

// ---------------------------------------------------------------- wire format

func encodeRemaining(n int) []byte {
	var out []byte
	for {
		b := byte(n % 128)
		n /= 128
		if n > 0 {
			b |= 0x80
		}
		out = append(out, b)
		if n == 0 {
			return out
		}
	}
}

func encodeString(s string) []byte {
	b := make([]byte, 2+len(s))
	binary.BigEndian.PutUint16(b, uint16(len(s)))
	copy(b[2:], s)
	return b
}

func packet(header byte, body []byte) []byte {
	out := []byte{header}
	out = append(out, encodeRemaining(len(body))...)
	return append(out, body...)
}

func connectPacket(clientID, user, pass string, keepAlive uint16) []byte {
	vh := encodeString("MQTT")
	vh = append(vh, mqttProtoLevel)
	flags := byte(0x02) // clean session
	if user != "" {
		flags |= 0x80
	}
	if pass != "" {
		flags |= 0x40
	}
	vh = append(vh, flags, byte(keepAlive>>8), byte(keepAlive))
	body := append(vh, encodeString(clientID)...)
	if user != "" {
		body = append(body, encodeString(user)...)
	}
	if pass != "" {
		body = append(body, encodeString(pass)...)
	}
	return packet(0x10, body)
}

func publishPacket(topic string, payload []byte) []byte {
	body := encodeString(topic)
	body = append(body, payload...)
	return packet(0x30, body) // QoS 0
}

func subscribePacket(id uint16, topics []string) []byte {
	body := []byte{byte(id >> 8), byte(id)}
	for _, t := range topics {
		body = append(body, encodeString(t)...)
		body = append(body, 0) // requested QoS 0
	}
	return packet(0x82, body)
}

func readPacket(br *bufio.Reader) (byte, []byte, error) {
	h, err := br.ReadByte()
	if err != nil {
		return 0, nil, err
	}
	mult, length := 1, 0
	for i := 0; i < 4; i++ {
		b, err := br.ReadByte()
		if err != nil {
			return 0, nil, err
		}
		length += int(b&0x7F) * mult
		if b&0x80 == 0 {
			break
		}
		mult *= 128
	}
	if length > 1<<20 {
		return 0, nil, fmt.Errorf("packet too large: %d", length)
	}
	p := make([]byte, length)
	if _, err := io.ReadFull(br, p); err != nil {
		return 0, nil, err
	}
	return h, p, nil
}

func parsePublish(h byte, p []byte) (string, []byte, error) {
	if len(p) < 2 {
		return "", nil, fmt.Errorf("short PUBLISH")
	}
	n := int(binary.BigEndian.Uint16(p))
	if len(p) < 2+n {
		return "", nil, fmt.Errorf("truncated topic")
	}
	topic := string(p[2 : 2+n])
	rest := p[2+n:]
	if qos := (h >> 1) & 3; qos > 0 {
		if len(rest) < 2 {
			return "", nil, fmt.Errorf("truncated packet id")
		}
		rest = rest[2:]
	}
	return topic, rest, nil
}
