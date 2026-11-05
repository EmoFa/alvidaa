# Bridge deploy runbook (on-TV `alvidaa-bridge`, armv7)

Executable end-to-end by one person with the repo and the root key.
Read [`LANES.md`](LANES.md) first for what the bridge is. Ground rules
apply: announce the md5 in the team bulletin before touching the TV,
never reboot as part of a deploy, home shell stays pristine (findings
12 §7).

## What you need

- This repo, with `server/keys/tv_root_ed25519` present (gitignored).
- `TV_HOST` set if the TV's DHCP lease moved (default `192.168.0.11`;
  ssh port 2222, user `root` — i.e. `./server/tv 'cmd'` works).
- Go toolchain for the armv7 cross-build.

## 1. Build and stage

```sh
cd bridge && go test ./... && cd ..
./tools/build-bridge.sh                 # -> bridge/dist/alvidaa-bridge-armv7
shasum -a 256 bridge/dist/alvidaa-bridge-armv7
md5 -q bridge/dist/alvidaa-bridge-armv7 # record this — announce it
```

`tools/build-bridge.sh` embeds the version (`v1.0-XX-g<hash>`) from
`git describe`; commit your work first so the binary is not `-dirty`.
The running bridge reports its version at `GET /api/health`
(`version` field) and as the first `bridge.log` line.

## 2. Announce

Post the md5 (and version) in the team bulletin **before** writing to
the TV. No other lane touches the TV during the deploy window.

## 3. Push (no ETXTBSY, minimal downtime)

The TV has no sftp/scp server — push over ssh `cat`. Write to a NEW
file, verify, then swap; overwriting the inode of a running binary
fails with `ETXTBSY`.

```sh
SSH="ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -p 2222 -i server/keys/tv_root_ed25519 root@$TV_HOST"

# 3a. backup the running binary on the TV (one .bak per deploy)
$SSH 'cp -p /var/local/alvidaa/alvidaa-bridge /var/local/alvidaa/alvidaa-bridge.bak-$(date +%Y%m%d-%H%M)'

# 3b. push to a staging path
rm -f /tmp/alvidaa-bridge-armv7.push   # ensure clean local pipe
$SSH 'cat > /var/local/alvidaa/alvidaa-bridge.new' < bridge/dist/alvidaa-bridge-armv7

# 3c. verify ON THE TV — must equal the announced md5
$SSH 'md5sum /var/local/alvidaa/alvidaa-bridge.new; chmod 755 /var/local/alvidaa/alvidaa-bridge.new'
```

## 4. Swap and restart with the exact flags

```sh
$SSH 'kill $(pidof alvidaa-bridge) 2>/dev/null; sleep 1
      mv /var/local/alvidaa/alvidaa-bridge.new /var/local/alvidaa/alvidaa-bridge
      /var/local/tvtools/busybox nohup /var/local/alvidaa/alvidaa-bridge \
        -keys /var/local/alvidaa/keys \
        -assets /var/local/alvidaa/launcher \
        -config /var/local/alvidaa/config.json \
        -addr 0.0.0.0:8770 \
        -mqtt 127.0.0.1:36669 >> /var/local/alvidaa/bridge.log 2>&1 &'
```

`nohup` matters: without it the dropbear session teardown can reap the
bridge the moment your ssh command returns. Flags are exact — `-addr
0.0.0.0:8770` (LAN reachability for verification) and `-mqtt
127.0.0.1:36669` (loopback TLS, one client identity: never start two).

## 5. Verify (from the Mac; the TV has no curl)

```sh
curl -s http://$TV_HOST:8770/api/health        # ok:true, version: v1.0-XX-g..., mqtt:true
curl -s -o /dev/null -w '%{http_code}\n' http://$TV_HOST:8770/icon/vidaa-recon   # 200
curl -s -o /dev/null -w '%{http_code}\n' http://$TV_HOST:8770/icon/2256          # 200 (Spotify, staged)
curl -s -o /dev/null -w '%{http_code}\n' http://$TV_HOST:8770/bg/bg2.png         # 200
curl -s -o /dev/null -w '%{http_code}\n' http://$TV_HOST:8770/next/app.html      # 200 (dir-index fix)
$SSH 'pidof alvidaa-bridge; head -1 /var/local/alvidaa/bridge.log'               # version line
```

Then press Home (or have the owner do it): the watcher bounce should
land on the launcher within ~1s. That is the end-to-end green.

## 6. Rollback

```sh
$SSH 'kill $(pidof alvidaa-bridge) 2>/dev/null; sleep 1
      cp -p /var/local/alvidaa/alvidaa-bridge.bak-<stamp> /var/local/alvidaa/alvidaa-bridge
      /var/local/tvtools/busybox nohup /var/local/alvidaa/alvidaa-bridge \
        -keys /var/local/alvidaa/keys -assets /var/local/alvidaa/launcher \
        -config /var/local/alvidaa/config.json -addr 0.0.0.0:8770 \
        -mqtt 127.0.0.1:36669 >> /var/local/alvidaa/bridge.log 2>&1 &'
```

Re-verify `/api/health` reports the OLD version. Never leave the TV
without a working bridge without saying so in the bulletin.

## Watchdog gap (PROPOSAL — awaiting ack, hook untouched)

Hook v12 (`tools/otaTest-hook.sh`) keeps the bridge alive only inside
two bounded loops: the early-start retry (~2 min, 60×2s) and the
watchdog (~20 min, 40×30s). After minute ~20 the loop exits; if the
bridge dies after that — crash, OOM, MQTT identity fight, bad config on
a manual restart — **nothing restarts it until the next reboot**, and
the same bounded loop is all that guards dropbear/telnetd (ssh access
itself expires at the same mark).

**Proposed minimal fix (one token):** unbind the watchdog loop —
`while [ $i -lt 40 ]` → `while [ 1 = 1 ]` in both the canonical template
(`tools/otaTest-hook.sh`) and the installer embed
(`launcher/hookinstall.html`). The loop body is already pidof-guarded
and idempotent (iptables `-C` checks), so an immortal loop costs one
sleeping shell process and cannot double-start anything. If the loop
itself dies we are no worse off than today. Heavier alternative
(APM/supervisor entry) touches vendor infra for no extra coverage.
Do not bump the hook to v13 until ds41 acks this.
