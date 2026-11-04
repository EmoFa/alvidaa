#!/usr/bin/env python3
"""Run commands over the TV's root shell (hook v3+ telnetd on 2323).

Usage: python3 tvshell.py "cmd1" "cmd2" ...
Sends each command, reads until a quiet window, prints the output.
This speaks plain TCP to busybox telnetd (-l /bin/sh) — no telnet IAC
negotiation is attempted beyond swallowing initial bytes.
"""
import os
import socket
import sys
import time

HOST = os.environ.get("TV_HOST")
PORT = 2323
if not HOST:
    sys.exit("set TV_HOST=<tv-ip> (the TV's LAN address)")
QUIET = 0.8      # seconds of silence before a command's output is considered done
MAXWAIT = 12.0

def drain(sock, quiet=QUIET, maxwait=MAXWAIT):
    sock.settimeout(quiet)
    out = b""
    deadline = time.time() + maxwait
    while time.time() < deadline:
        try:
            chunk = sock.recv(65536)
            if not chunk:
                break
            out += chunk
            deadline = min(deadline, time.time() + quiet + 0.2)
        except socket.timeout:
            if out:
                break
    return out

def main():
    cmds = sys.argv[1:]
    if not cmds:
        sys.exit("usage: tvshell.py \"cmd\" ...")
    s = socket.create_connection((HOST, PORT), timeout=6)
    s.settimeout(2)
    try:  # swallow telnet IAC negotiation / banner
        time.sleep(0.4)
        s.recv(4096)
    except OSError:
        pass
    for cmd in cmds:
        s.sendall((cmd + "\n").encode())
        out = drain(s)
        text = out.decode(errors="replace")
        # strip the echoed command if telnetd echoes it
        if text.startswith(cmd):
            text = text[len(cmd):]
        print(f"$ {cmd}\n{text.rstrip()}\n", flush=True)
    s.close()

if __name__ == "__main__":
    main()
