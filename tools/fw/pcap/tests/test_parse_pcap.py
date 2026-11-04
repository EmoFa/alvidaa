"""Synthetic pcap/pcapng fixtures for parse_pcap.py (no network, no real data)."""

import json
import socket
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import parse_pcap  # noqa: E402


def _ipv4(protocol, payload):
    total_length = 20 + len(payload)
    header = struct.pack(
        ">BBHHHBBH4s4s",
        0x45,
        0,
        total_length,
        0x1234,
        0x4000,
        64,
        protocol,
        0,
        socket.inet_aton("198.51.100.10"),
        socket.inet_aton("198.51.100.20"),
    )
    return header + payload


def _udp(sport, dport, payload):
    return struct.pack(">HHHH", sport, dport, 8 + len(payload), 0) + payload


def _tcp(sport, dport, payload):
    offset_flags = (5 << 12) | 0x18  # data offset 5, PSH+ACK
    return struct.pack(">HHIIHHHH", sport, dport, 1, 0, offset_flags, 65535, 0, 0) + payload


def _ethernet(payload, ethertype=0x0800):
    destination = b"\x02\x00\x00\x00\x00\x02"
    source = b"\x02\x00\x00\x00\x00\x01"
    return destination + source + struct.pack(">H", ethertype) + payload


def _dns_query(name):
    qname = b"".join(bytes([len(label)]) + label.encode("ascii") for label in name.split("."))
    return (
        struct.pack(">HHHHHH", 0x1234, 0x0100, 1, 0, 0, 0)
        + qname
        + b"\x00"
        + struct.pack(">HH", 1, 1)
    )


def _tls_client_hello(server_name):
    name = server_name.encode("ascii")
    entry = b"\x00" + struct.pack(">H", len(name)) + name
    server_name_list = struct.pack(">H", len(entry)) + entry
    sni_extension = struct.pack(">HH", 0, len(server_name_list)) + server_name_list
    extensions = sni_extension
    body = (
        b"\x03\x03"
        + b"\x11" * 32
        + b"\x00"
        + struct.pack(">H", 2)
        + b"\x13\x01"
        + b"\x01\x00"
        + struct.pack(">H", len(extensions))
        + extensions
    )
    handshake = b"\x01" + len(body).to_bytes(3, "big") + body
    return b"\x16\x03\x01" + len(handshake).to_bytes(2, "big") + handshake


def _http_request():
    return b"GET / HTTP/1.1\r\nHost: web.example.test\r\nConnection: close\r\n\r\n"


def _frames():
    dns = _ethernet(_ipv4(17, _udp(53000, 53, _dns_query("example.test"))))
    tls = _ethernet(_ipv4(6, _tcp(53001, 443, _tls_client_hello("tls.example.test"))))
    http = _ethernet(_ipv4(6, _tcp(53002, 80, _http_request())))
    return [dns, tls, http]


def _pcap(frames):
    output = [struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1)]
    for frame in frames:
        output.append(struct.pack("<IIII", 0, 0, len(frame), len(frame)))
        output.append(frame)
    return b"".join(output)


def _block(block_type, body):
    padding = b"\x00" * ((-len(body)) % 4)
    total_length = 12 + len(body) + len(padding)
    return (
        struct.pack("<II", block_type, total_length)
        + body
        + padding
        + struct.pack("<I", total_length)
    )


def _pcapng(frames):
    section = _block(
        0x0A0D0D0A,
        struct.pack("<IHHQ", 0x1A2B3C4D, 1, 0, 0xFFFFFFFFFFFFFFFF),
    )
    interface = _block(1, struct.pack("<HHI", 1, 0, 65535))
    blocks = [section, interface]
    for frame in frames:
        packet = struct.pack("<IIIII", 0, 0, 0, len(frame), len(frame)) + frame
        blocks.append(_block(6, packet))
    return b"".join(blocks)


def _assert_result(result, fmt):
    assert result["format"] == fmt
    assert result["capture"] == "sample." + fmt
    assert result["dns"] == [{"name": "example.test", "count": 1}]
    assert result["tls_sni"] == [{"name": "tls.example.test", "count": 1}]
    assert result["http_host"] == [{"name": "web.example.test", "count": 1}]


def test_analyze_pcap(tmp_path):
    path = tmp_path / "sample.pcap"
    path.write_bytes(_pcap(_frames()))
    _assert_result(parse_pcap.analyze(str(path)), "pcap")


def test_analyze_pcapng(tmp_path):
    path = tmp_path / "sample.pcapng"
    path.write_bytes(_pcapng(_frames()))
    _assert_result(parse_pcap.analyze(str(path)), "pcapng")


def test_cli_json_and_out(tmp_path, capsys):
    capture = tmp_path / "sample.pcap"
    capture.write_bytes(_pcap(_frames()))

    assert parse_pcap.main([str(capture), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["dns"][0]["name"] == "example.test"

    report = tmp_path / "report.json"
    assert parse_pcap.main([str(capture), "--json", "--out", str(report)]) == 0
    written = json.loads(report.read_text(encoding="utf-8"))
    assert written["http_host"][0]["name"] == "web.example.test"
