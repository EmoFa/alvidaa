# pcap host extractor

`parse_pcap.py` is a small, standard-library-only CLI that summarises host
names seen in a packet capture. It is intended for local research on captures
you are authorised to inspect.

## What it extracts

- DNS question names (UDP port 53, query packets only).
- TLS server names from the ClientHello SNI extension (TCP port 443).
- HTTP/1.x `Host` header values (TCP port 80).

The report contains only the extracted names and their occurrence counts. It
does not print or write packet payloads, IP addresses, MAC addresses, or TCP
connection lists.

## Usage

```sh
python tools/pcap/parse_pcap.py capture.pcap
python tools/pcap/parse_pcap.py capture.pcapng --json
python tools/pcap/parse_pcap.py capture.pcap --json --out report.json
```

Both classic pcap (little/big endian, microsecond/nanosecond timestamps) and
pcapng (section, interface, enhanced packet, simple packet blocks) are read.
Supported link layers: Ethernet, RAW, NULL/AF_INET, Linux SLL/SLL2, and
LINKTYPE_IPV4. Only IPv4 is parsed.

## Limitations

- No IPv6.
- No TCP stream reassembly: a ClientHello split across TCP segments is missed,
  and HTTP `Host` is only found in the first request line block of a segment.
- TLS SNI is only checked on TCP destination port 443; HTTP only on port 80.
- Encrypted or tunnelled DNS/HTTP cannot be extracted.
- Only the first question of each DNS message and the first SNI entry are
  returned per packet.

## Privacy

Packet captures routinely contain personal data: IP addresses, MAC addresses,
host names, cookies, credentials, and full application payloads. Treat every
capture as sensitive. This tool reduces the output to host names, but the
result can still reveal browsing and device behaviour.

- Do not publish raw captures.
- Do not commit captures or generated reports to a public repository.
- Share only the minimum extracted evidence needed for a finding.
- Check local law and the consent of the network owner before capturing.
