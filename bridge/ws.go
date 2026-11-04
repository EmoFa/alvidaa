// Minimal WebSocket server: text frames only, which is all the overlay uses.
package main

import (
	"bufio"
	"crypto/sha1"
	"encoding/base64"
	"encoding/binary"
	"fmt"
	"io"
	"net"
	"net/http"
	"sync"
)

const wsGUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

type WSConn struct {
	conn net.Conn
	br   *bufio.Reader
	mu   sync.Mutex
}

func wsAccept(key string) string {
	h := sha1.Sum([]byte(key + wsGUID))
	return base64.StdEncoding.EncodeToString(h[:])
}

// upgrade performs the handshake and returns a connection the caller owns.
func upgrade(w http.ResponseWriter, r *http.Request) (*WSConn, error) {
	key := r.Header.Get("Sec-WebSocket-Key")
	if key == "" || r.Header.Get("Upgrade") == "" {
		return nil, fmt.Errorf("websocket upgrade required")
	}
	hj, ok := w.(http.Hijacker)
	if !ok {
		return nil, fmt.Errorf("hijacking unsupported")
	}
	conn, buf, err := hj.Hijack()
	if err != nil {
		return nil, err
	}
	resp := "HTTP/1.1 101 Switching Protocols\r\n" +
		"Upgrade: websocket\r\n" +
		"Connection: Upgrade\r\n" +
		"Sec-WebSocket-Accept: " + wsAccept(key) + "\r\n\r\n"
	if _, err := buf.WriteString(resp); err != nil {
		conn.Close()
		return nil, err
	}
	if err := buf.Flush(); err != nil {
		conn.Close()
		return nil, err
	}
	return &WSConn{conn: conn, br: buf.Reader}, nil
}

func (c *WSConn) Close() error { return c.conn.Close() }

// ReadText returns the next text frame. Control frames are handled inline.
func (c *WSConn) ReadText() ([]byte, error) {
	for {
		hdr := make([]byte, 2)
		if _, err := io.ReadFull(c.br, hdr); err != nil {
			return nil, err
		}
		opcode := hdr[0] & 0x0F
		masked := hdr[1]&0x80 != 0
		length := uint64(hdr[1] & 0x7F)
		switch length {
		case 126:
			var b [2]byte
			if _, err := io.ReadFull(c.br, b[:]); err != nil {
				return nil, err
			}
			length = uint64(binary.BigEndian.Uint16(b[:]))
		case 127:
			var b [8]byte
			if _, err := io.ReadFull(c.br, b[:]); err != nil {
				return nil, err
			}
			length = binary.BigEndian.Uint64(b[:])
		}
		if length > 1<<20 {
			return nil, fmt.Errorf("frame too large: %d", length)
		}
		var mask [4]byte
		if masked {
			if _, err := io.ReadFull(c.br, mask[:]); err != nil {
				return nil, err
			}
		}
		data := make([]byte, length)
		if _, err := io.ReadFull(c.br, data); err != nil {
			return nil, err
		}
		if masked {
			for i := range data {
				data[i] ^= mask[i%4]
			}
		}

		switch opcode {
		case 0x8: // close
			return nil, io.EOF
		case 0x9: // ping -> pong
			if err := c.write(0xA, data); err != nil {
				return nil, err
			}
			continue
		case 0xA: // pong
			continue
		case 0x1: // text
			return data, nil
		default:
			return nil, fmt.Errorf("unsupported opcode %#x", opcode)
		}
	}
}

func (c *WSConn) SendText(payload []byte) error { return c.write(0x1, payload) }

func (c *WSConn) write(opcode byte, payload []byte) error {
	n := len(payload)
	var hdr []byte
	switch {
	case n < 126:
		hdr = []byte{0x80 | opcode, byte(n)}
	case n < 65536:
		hdr = []byte{0x80 | opcode, 126, byte(n >> 8), byte(n)}
	default:
		hdr = make([]byte, 10)
		hdr[0], hdr[1] = 0x80|opcode, 127
		binary.BigEndian.PutUint64(hdr[2:], uint64(n))
	}
	c.mu.Lock()
	defer c.mu.Unlock()
	if _, err := c.conn.Write(hdr); err != nil {
		return err
	}
	_, err := c.conn.Write(payload)
	return err
}
