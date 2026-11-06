# 01 — SSDP descriptor (2026-11-06)

First on-LAN probe of the TV beyond the passive fingerprint. Read-only:
an SSDP M-SEARCH (UDP multicast) plus an HTTP GET of the descriptor XML,
via `tools/ssdp-descriptor.sh`. Nothing was written to the TV.

## How it was captured

Direct-IP mode found no descriptor on any of the common VIDAA UPnP ports
(49152–49154, 8080, 1400, 2869):

```
$ tools/ssdp-descriptor.sh 10.0.0.173
None of 49152/49153/49154/8080/1400/2869 answered.
```

Auto-discovery (SSDP M-SEARCH) then located the real descriptor on a
non-standard port:

```
$ tools/ssdp-descriptor.sh
Responders:
  10.0.0.1      http://10.0.0.1:2189/rootDesc.xml      (FreeBSD/MiniUPnPd router — not the TV)
  10.0.0.173    http://10.0.0.173:3366/dd.xml
```

## TV descriptor — `http://10.0.0.173:3366/dd.xml` (417 bytes)

```
friendlyName:  TV
modelName:     75U8QE
manufacturer:  Hisense
UDN:           uuid:65343861-3933-3663-3137-346365343861
deviceType:    urn:schemas-upnp-org:device:tvdevice:1
serviceList:   (none)
transport_protocol: (not present)
```

## Readings

- **`modelName` is `75U8QE`, not the `75U8QTUK` retail sticker.** The SSDP
  descriptor reports the base panel/platform model; `U8QTUK` is the UK
  retail SKU dressing on the same panel. Consistent, not a conflict —
  record both.
- **No `transport_protocol` in this descriptor.** The onboarding ladder
  expected `≥ 3290` (it gates the `pair.py` credential cascade), but this
  build's `dd.xml` is a minimal 417-byte stub with no such field and an
  empty `serviceList`. On this firmware the transport-protocol digit is
  not exposed over UPnP; it has to come from the pairing handshake
  instead. Since **Sidee already handled pairing** (session persisted at
  `~/.sidee/session.json`, `auth_profile: modern`), the credential cascade
  this field would have steered is already resolved — the gap is cosmetic
  for our path, not a blocker.
- **Empty `serviceList`** — no DIAL / UPnP AV / WANIPConnection services
  advertised by the TV itself. Expected for a VIDAA set in default LAN
  posture; the control surface is the RemoteNow MQTT endpoint on
  `36669/tcp` (see findings/00), not UPnP.
- The second responder (`10.0.0.1:2189`, "FreeBSD router", MiniUPnPd
  2.3.9) is the owner's own gateway, not the TV. Its identifying fields
  are deliberately omitted here.

## State change

- `transport_protocol` inventory field: `untested` →
  `not-exposed-over-SSDP (dd.xml stub; pairing handled by Sidee)`.
- No capability flags change — this was a descriptor read only.

## Next

- `02-pairing.md` — confirm the Sidee-held session against the TV
  (state / applist round-trip via the Sidee app), record which credential
  profile is live (`modern`, per the session file). `server/pair.py` is
  **not** run — one MQTT server per TV, and Sidee holds it.
