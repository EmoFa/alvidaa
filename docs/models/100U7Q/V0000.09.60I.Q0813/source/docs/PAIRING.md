# Pairing (step 0)

Everything in this repository needs one thing that cannot be shipped: an
authorised MQTT session for **your** TV. This document is the complete path.

Time: a few minutes. No account, no cloud service, nothing leaves the LAN.

## What pairing is

The TV exposes a control interface over MQTT/TLS on port 36669. A client
authenticates with a certificate and then authorises itself with a PIN shown on
the TV. After approval the TV issues tokens, which the client stores in
`~/.sidee/session.json`.

Two properties matter:

- The **client certificate** comes from the vendor app. We do not ship it, and
  neither should you pass it around. [sidee](https://github.com/alvidaa/sidee)
  carries its own copy and provisions it on first start.
- The **session** is per TV. It contains tokens for your device. Never commit
  it, never paste it into an issue.

## Step by step

### 1. Get sidee

```sh
git clone https://github.com/alvidaa/sidee /tmp/sidee-check
cd /tmp/sidee-check && python3 -m pip install -r requirements.txt
```

Start it once (`python3 sidee.py`) so it provisions its client certificate,
then close it. Check:

```sh
python3 - <<'PY'
import sys; sys.path.insert(0, '/tmp/sidee-check')
from core import client
print('certificate:', client.has_client_certificate())
PY
```

### 2. Find the TV's addresses

- **IP**: router DHCP table or the TV's network settings.
- **Ethernet MAC**: TV settings, or from this machine
  `ip neigh show <tv-ip>` after a ping.

The TV accepts only the **Ethernet MAC with colons** as its identity
(`<tv-mac>`). A retail model number or a random UUID does not work.

### 3. Pair

```sh
cd <repo-root>
./scripts/pair.sh --tv <tv-ip> --sidee /tmp/sidee-check
```

or directly:

```sh
cd /tmp/sidee-check && python3 sidee.py pair <tv-ip>
```

The TV displays a four-digit PIN. Enter it once.

**Do not retrigger the request.** Each retrigger rotates the PIN, and several
wrong PINs lock the client out temporarily (`rc=5 NOT AUTHORIZED`). If that
happens, wait and start over with a fresh request.

### 4. Verify the session

```sh
ls -l ~/.sidee/session.json      # should be mode 600
```

You do not need to read it. If the file exists and `pair` reported success, the
next step will work.

### 5. Continue with the installer

```sh
./scripts/install.sh \
    --pubkey "ssh-ed25519 <PUBKEY> you@host" \
    --host <host-ip> \
    --tv <tv-ip> \
    --launch
```

`--launch` uses the paired session to install and open the install tile. Without
it, open `http://<host>:9000/install.html` on the TV yourself.

## Troubleshooting

| Symptom | Cause |
|---|---|
| `pair` returns `rc=5` | wrong PIN too often, or a retrigger rotated it; wait and start over |
| TV not found | wrong IP, TV asleep, or client on a different VLAN |
| `client.has_client_certificate()` is false | sidee was never started once, so it has not provisioned its certificate |
| Pairing works, `--launch` fails | the session belongs to a different TV (clone it per device) |

## What is deliberately not here

No certificate, no key, no token, no session and no device identifier. Those are
per-device or vendor material; obtain them yourself and keep them local.
