#!/usr/bin/env python3
"""Summarise host names observed in a pcap or pcapng capture.

Extracted data:
  * DNS question names (UDP port 53)
  * TLS server names from ClientHello SNI (TCP port 443)
  * HTTP/1.x ``Host`` header values (TCP port 80)

Only the names and their occurrence counts are reported.  Packet payloads are
parsed in memory and are never printed or written, so the output is far less
sensitive than the capture itself.

Usage:
    parse_pcap.py CAPTURE [--json] [--out PATH]
"""

from __future__ import annotations

import argparse
import json
import os
import struct
import sys

PCAPNG_MAGIC = b"\x0a\x0d\x0d\x0a"
PCAP_ENDIAN = {
    b"\xd4\xc3\xb2\xa1": "<",  # microsecond timestamps, little-endian
    b"\xa1\xb2\xc3\xd4": ">",  # microsecond timestamps, big-endian
    b"\x4d\x3c\xb2\xa1": "<",  # nanosecond timestamps, little-endian
    b"\xa1\xb2\x3c\x4d": ">",  # nanosecond timestamps, big-endian
}

LINKTYPE_NULL = 0
LINKTYPE_ETHERNET = 1
LINKTYPE_RAW = 101
LINKTYPE_LINUX_SLL = 113
LINKTYPE_IPV4 = 228
LINKTYPE_LINUX_SLL2 = 276

_ETHERTYPE_IPV4 = 0x0800
_ETHERTYPE_VLAN = (0x8100, 0x88A8)
_ETHERTYPE_PPPOE = 0x8864

_HTTP_METHOD_PREFIXES = (
    b"GET ",
    b"POST",
    b"HEAD",
    b"PUT ",
    b"DELE",
    b"OPTI",
    b"PATC",
    b"TRAC",
    b"CONN",
)


class PcapError(Exception):
    """Raised when the capture is malformed or uses an unsupported format."""


def _detect_format(data):
    if len(data) >= 4 and data[:4] == PCAPNG_MAGIC:
        return "pcapng"
    if len(data) >= 4 and data[:4] in PCAP_ENDIAN:
        return "pcap"
    raise PcapError("not a pcap or pcapng file")


def _iter_pcap(data):
    endian = PCAP_ENDIAN[data[:4]]
    if len(data) < 24:
        raise PcapError("truncated pcap global header")
    linktype = struct.unpack_from(endian + "I", data, 20)[0]
    offset = 24
    while offset + 16 <= len(data):
        included = struct.unpack_from(endian + "I", data, offset + 8)[0]
        offset += 16
        if included > len(data) - offset:
            raise PcapError("truncated pcap packet record")
        yield linktype, data[offset:offset + included]
        offset += included


def _iter_pcapng(data):
    endian = None
    interfaces = []
    offset = 0
    while offset + 12 <= len(data):
        if data[offset:offset + 4] == PCAPNG_MAGIC:
            byte_order_magic = data[offset + 8:offset + 12]
            if byte_order_magic == b"\x4d\x3c\x2b\x1a":
                endian = "<"
            elif byte_order_magic == b"\x1a\x2b\x3c\x4d":
                endian = ">"
            else:
                raise PcapError("invalid pcapng byte-order magic")
            interfaces = []
        if endian is None:
            raise PcapError("pcapng data before section header")
        block_type, block_length = struct.unpack_from(endian + "II", data, offset)
        if block_length < 12 or block_length % 4 or offset + block_length > len(data):
            raise PcapError("invalid pcapng block length")
        trailing = struct.unpack_from(endian + "I", data, offset + block_length - 4)[0]
        if trailing != block_length:
            raise PcapError("pcapng block length mismatch")

        if block_type == 1:  # Interface Description Block
            if block_length < 20:
                raise PcapError("truncated pcapng interface block")
            linktype = struct.unpack_from(endian + "H", data, offset + 8)[0]
            interfaces.append(linktype)
        elif block_type == 6:  # Enhanced Packet Block
            if block_length < 32:
                raise PcapError("truncated pcapng packet block")
            interface_id, _ts_high, _ts_low, captured, _original = struct.unpack_from(
                endian + "IIIII", data, offset + 8
            )
            if interface_id >= len(interfaces):
                raise PcapError("pcapng packet references unknown interface")
            start = offset + 28
            if start + captured > offset + block_length - 4:
                raise PcapError("pcapng packet data exceeds block")
            yield interfaces[interface_id], data[start:start + captured]
        elif block_type == 3:  # Simple Packet Block (interface 0)
            if block_length < 16:
                raise PcapError("truncated pcapng simple packet block")
            if not interfaces:
                raise PcapError("pcapng simple packet block without interface")
            original = struct.unpack_from(endian + "I", data, offset + 8)[0]
            available = block_length - 16
            captured = min(original, available)
            yield interfaces[0], data[offset + 12:offset + 12 + captured]

        offset += block_length


def iter_packets(data):
    """Yield ``(linktype, frame_bytes)`` tuples from pcap or pcapng data."""
    if _detect_format(data) == "pcapng":
        yield from _iter_pcapng(data)
    else:
        yield from _iter_pcap(data)


def _ethernet_payload(frame):
    if len(frame) < 14:
        return None
    ethertype = struct.unpack_from(">H", frame, 12)[0]

    # Some consumer-router captures prepend an 8-byte link-layer header.
    if ethertype != _ETHERTYPE_IPV4 and len(frame) >= 22:
        if struct.unpack_from(">H", frame, 20)[0] == _ETHERTYPE_IPV4:
            frame = frame[8:]
            ethertype = struct.unpack_from(">H", frame, 12)[0]

    while ethertype in _ETHERTYPE_VLAN:
        if len(frame) < 18:
            return None
        ethertype = struct.unpack_from(">H", frame, 16)[0]
        frame = frame[4:]

    if ethertype == _ETHERTYPE_IPV4:
        return frame[14:]
    if ethertype == _ETHERTYPE_PPPOE:
        if len(frame) < 22:
            return None
        ppp_protocol = struct.unpack_from(">H", frame, 20)[0]
        return frame[22:] if ppp_protocol == 0x0021 else None
    return None


def _network_payload(linktype, frame):
    if linktype == LINKTYPE_ETHERNET:
        return _ethernet_payload(frame)
    if linktype == LINKTYPE_RAW:
        return frame if frame[:1] and frame[0] >> 4 == 4 else None
    if linktype == LINKTYPE_IPV4:
        return frame
    if linktype == LINKTYPE_NULL:
        if len(frame) < 4:
            return None
        family = struct.unpack_from("<I", frame, 0)[0]
        return frame[4:] if family in (2, 0x02000000) else None  # AF_INET
    if linktype == LINKTYPE_LINUX_SLL:
        if len(frame) < 16:
            return None
        protocol = struct.unpack_from(">H", frame, 14)[0]
        return frame[16:] if protocol == _ETHERTYPE_IPV4 else None
    if linktype == LINKTYPE_LINUX_SLL2:
        if len(frame) < 20:
            return None
        protocol = struct.unpack_from(">H", frame, 0)[0]
        return frame[20:] if protocol == _ETHERTYPE_IPV4 else None
    return None


def _parse_ipv4(packet):
    """Return ``(protocol, sport, dport, payload)`` or ``None``."""
    if len(packet) < 20 or packet[0] >> 4 != 4:
        return None
    header_length = (packet[0] & 0x0F) * 4
    if header_length < 20 or header_length > len(packet):
        return None
    total_length = struct.unpack_from(">H", packet, 2)[0]
    if header_length <= total_length <= len(packet):
        packet = packet[:total_length]

    protocol = packet[9]
    if protocol == 6:  # TCP
        if len(packet) < header_length + 20:
            return None
        sport, dport = struct.unpack_from(">HH", packet, header_length)
        data_offset = (packet[header_length + 12] >> 4) * 4
        if data_offset < 20 or header_length + data_offset > len(packet):
            return None
        return "tcp", sport, dport, packet[header_length + data_offset:]
    if protocol == 17:  # UDP
        if len(packet) < header_length + 8:
            return None
        sport, dport, udp_length = struct.unpack_from(">HHH", packet, header_length)
        end = header_length + udp_length
        if udp_length < 8 or end > len(packet):
            end = len(packet)
        return "udp", sport, dport, packet[header_length + 8:end]
    return None


def _parse_packet(linktype, frame):
    payload = _network_payload(linktype, frame)
    if payload is None:
        return None
    return _parse_ipv4(payload)


def _read_dns_name(message, offset):
    """Return ``(name, next_offset)`` for one DNS name, or ``(None, offset)``."""
    labels = []
    next_offset = None
    seen = set()
    while True:
        if offset >= len(message):
            return None, offset
        length = message[offset]
        if length == 0:
            if next_offset is None:
                next_offset = offset + 1
            break
        if (length & 0xC0) == 0xC0:
            if offset + 1 >= len(message):
                return None, offset
            pointer = ((length & 0x3F) << 8) | message[offset + 1]
            if next_offset is None:
                next_offset = offset + 2
            if pointer in seen or pointer >= len(message):
                return None, next_offset
            seen.add(pointer)
            offset = pointer
            continue
        if length > 63 or offset + 1 + length > len(message):
            return None, next_offset or offset
        labels.append(message[offset + 1:offset + 1 + length].decode("ascii", "replace"))
        offset += 1 + length
    if not labels:
        return None, next_offset or offset
    return ".".join(labels), next_offset


def parse_dns_questions(message):
    """Return DNS QNAMEs from a UDP DNS query message."""
    if len(message) < 12:
        return []
    flags, question_count = struct.unpack_from(">HH", message, 2)
    if flags & 0x8000 or question_count == 0:
        return []
    offset = 12
    names = []
    for _ in range(question_count):
        name, offset = _read_dns_name(message, offset)
        if name:
            names.append(name)
        if offset is None or offset + 4 > len(message):
            break
        offset += 4  # QTYPE + QCLASS
    return names


def parse_tls_sni(payload):
    """Return the SNI host name from a TLS ClientHello record, or ``None``."""
    if len(payload) < 9 or payload[0] != 0x16 or payload[5] != 0x01:
        return None

    offset = 5 + 4 + 2 + 32
    if offset + 1 > len(payload):
        return None
    session_length = payload[offset]
    offset += 1 + session_length
    if offset + 2 > len(payload):
        return None
    cipher_length = struct.unpack_from(">H", payload, offset)[0]
    offset += 2 + cipher_length
    if offset + 1 > len(payload):
        return None
    compression_length = payload[offset]
    offset += 1 + compression_length
    if offset + 2 > len(payload):
        return None
    extensions_length = struct.unpack_from(">H", payload, offset)[0]
    offset += 2
    end = min(offset + extensions_length, len(payload))

    while offset + 4 <= end:
        extension_type, extension_length = struct.unpack_from(">HH", payload, offset)
        offset += 4
        if extension_type == 0 and offset + 5 <= end:
            name_length = struct.unpack_from(">H", payload, offset + 3)[0]
            start = offset + 5
            if start + name_length > end:
                return None
            return payload[start:start + name_length].decode("ascii", "replace")
        offset += extension_length
    return None


def parse_http_host(payload):
    """Return the ``Host`` header of an HTTP/1.x request, or ``None``."""
    if not payload.startswith(_HTTP_METHOD_PREFIXES):
        return None
    head = payload.split(b"\r\n\r\n", 1)[0]
    for line in head.split(b"\r\n")[1:]:
        if line.lower().startswith(b"host:"):
            value = line.split(b":", 1)[1].strip()
            return value.decode("ascii", "replace") if value else None
    return None


def analyze(path):
    """Analyse one capture and return a JSON-serialisable result dict."""
    with open(path, "rb") as handle:
        data = handle.read()
    capture_format = _detect_format(data)

    dns = {}
    sni = {}
    http = {}
    for linktype, frame in iter_packets(data):
        parsed = _parse_packet(linktype, frame)
        if parsed is None:
            continue
        protocol, sport, dport, payload = parsed
        if protocol == "udp" and 53 in (sport, dport):
            for name in parse_dns_questions(payload):
                dns[name] = dns.get(name, 0) + 1
        elif protocol == "tcp":
            if dport == 443:
                name = parse_tls_sni(payload)
                if name:
                    sni[name] = sni.get(name, 0) + 1
            elif dport == 80:
                name = parse_http_host(payload)
                if name:
                    http[name] = http.get(name, 0) + 1

    def items(counter):
        return [
            {"name": name, "count": count}
            for name, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))
        ]

    return {
        "capture": os.path.basename(path),
        "format": capture_format,
        "dns": items(dns),
        "tls_sni": items(sni),
        "http_host": items(http),
    }


def _render_text(result):
    lines = ["capture: %s (%s)" % (result["capture"], result["format"])]
    for key, title in (
        ("dns", "DNS qnames"),
        ("tls_sni", "TLS SNI"),
        ("http_host", "HTTP Host headers"),
    ):
        lines.append("")
        lines.append(title + ":")
        if not result[key]:
            lines.append("  (none)")
        else:
            for entry in result[key]:
                lines.append("  %5d  %s" % (entry["count"], entry["name"]))
    return "\n".join(lines)


def _build_parser():
    parser = argparse.ArgumentParser(
        description="Extract DNS qnames, TLS SNI and HTTP Host values from a capture.",
        epilog="Only host names and counts are printed; packet payloads are never dumped.",
    )
    parser.add_argument("capture", metavar="FILE", help="input .pcap or .pcapng file")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
    parser.add_argument("--out", metavar="PATH", help="write the report to PATH")
    return parser


def main(argv=None):
    args = _build_parser().parse_args(argv)
    try:
        result = analyze(args.capture)
    except (OSError, PcapError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2

    if args.json:
        output = json.dumps(result, indent=2, ensure_ascii=False)
    else:
        output = _render_text(result)

    if args.out:
        try:
            with open(args.out, "w", encoding="utf-8") as handle:
                handle.write(output + "\n")
        except OSError as exc:
            print("error: cannot write report: %s" % exc, file=sys.stderr)
            return 2
        print("wrote %s" % args.out, file=sys.stderr)
    else:
        print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
