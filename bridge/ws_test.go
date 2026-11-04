package main

import (
	"bufio"
	"encoding/binary"
	"io"
	"net"
	"testing"
	"time"
)

func TestWSFrameRoundTrip(t *testing.T) {
	serverSide, clientSide := net.Pipe()
	ws := &WSConn{conn: serverSide, br: bufio.NewReader(serverSide)}

	want := []byte(`{"t":"hello","apps":[]}`)
	go func() {
		mask := [4]byte{1, 2, 3, 4}
		hdr := []byte{0x81, 0x80 | byte(len(want))}
		frame := append(hdr, mask[:]...)
		payload := make([]byte, len(want))
		for i := range want {
			payload[i] = want[i] ^ mask[i%4]
		}
		frame = append(frame, payload...)
		clientSide.Write(frame)
	}()

	got, err := ws.ReadText()
	if err != nil {
		t.Fatal(err)
	}
	if string(got) != string(want) {
		t.Fatalf("got %q want %q", got, want)
	}
}

func TestWSExtendedLengthAndPing(t *testing.T) {
	serverSide, clientSide := net.Pipe()
	ws := &WSConn{conn: serverSide, br: bufio.NewReader(serverSide)}

	pongs := make(chan []byte, 1)
	go func() {
		br := bufio.NewReader(clientSide)
		h, p, err := readFrame(br)
		if err == nil && h&0x0F == 0xA {
			pongs <- p
		}
	}()

	go func() {
		clientSide.Write(maskFrame(0x89, []byte("hi"))) // ping
		clientSide.Write(maskFrame(0x81, []byte("after-ping")))
	}()

	got, err := ws.ReadText()
	if err != nil {
		t.Fatal(err)
	}
	if string(got) != "after-ping" {
		t.Fatalf("got %q", got)
	}

	select {
	case p := <-pongs:
		if string(p) != "hi" {
			t.Fatalf("pong payload = %q", p)
		}
	case <-time.After(2 * time.Second):
		t.Fatal("no pong written")
	}
}

func maskFrame(opcode byte, payload []byte) []byte {
	mask := [4]byte{4, 3, 2, 1}
	frame := []byte{0x80 | opcode, 0x80 | byte(len(payload))}
	frame = append(frame, mask[:]...)
	for i, v := range payload {
		frame = append(frame, v^mask[i%4])
	}
	return frame
}

func readFrame(br *bufio.Reader) (byte, []byte, error) {
	hdr, err := br.ReadByte()
	if err != nil {
		return 0, nil, err
	}
	n, err := br.ReadByte()
	if err != nil {
		return 0, nil, err
	}
	length := int(n & 0x7F)
	if length == 126 {
		var b [2]byte
		if _, err := io.ReadFull(br, b[:]); err != nil {
			return 0, nil, err
		}
		length = int(binary.BigEndian.Uint16(b[:]))
	}
	p := make([]byte, length)
	_, err = io.ReadFull(br, p)
	return hdr, p, err
}

func TestWSRejectsOversizedFrame(t *testing.T) {
	serverSide, clientSide := net.Pipe()
	ws := &WSConn{conn: serverSide, br: bufio.NewReader(serverSide)}
	go func() {
		hdr := []byte{0x81, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF}
		clientSide.Write(hdr)
	}()
	done := make(chan error, 1)
	go func() {
		_, err := ws.ReadText()
		done <- err
	}()
	select {
	case err := <-done:
		if err == nil {
			t.Fatal("expected an error for an oversized frame")
		}
	case <-time.After(2 * time.Second):
		t.Fatal("ReadText hung on an oversized frame")
	}
}
