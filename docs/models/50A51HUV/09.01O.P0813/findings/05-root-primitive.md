# alvidaa findings — the console gate, the root primitive, and the harvest (recon §10.9–10.12)

> Split from the original FINDINGS.md lab notebook. Canonical record; the blog and STORY.md draw from these.

### 10.9 v7 results: the console gate, and the root primitive

- **The UART root shell gate is `key_check.sh` and it is fully understood.**
  `main()` = USB-key auth → `source /etc/profile; /bin/sh` (root shell). The key
  file must sit in the root of a mounted FAT32 USB (`/tmp/lo_*/`), named
  `md5(vendorID + productID + tvModel)` (model from
  `/hidata/critical/config/critical.ini`), content validated by
  `/usr/local/bin/check_usb_key` (binary, not yet exfiltrated — binary reads
  crash the bridge). There is an interactive **`dummy`** fallback (error codes
  2/9/12 → type `dummy`, `auth`, PIN, key) that also ends in `check_usb_key`.
  Success also calls `envAccess UARTOnOff on` — UART output is env-gated.
  `/tmp` is a tmpfs the bridge can write, so key *placement* is no obstacle —
  the content check is the only gate.
- **The OEM white-name map is data-only** (pic/sound/panel/EDID .ini/.bin/.jpg
  destinations) — the OEM deployer is a root file-write into middleware-parsed
  configs, not an exec primitive. `security-dac-oem.sh` shows the expected DAC
  of those destinations.
- **`rc.local` (root, every boot) executes `/var/local/otaTest.sh` if present** —
  and `/var/local` is bridge-writable. That is the root code-exec primitive:
  write the script through the bridge, reboot, root. (Presumably an OTA
  auto-test hook left in production.)
- rc.local also: starts `sshd`+`telnetd` from `/usr/local/bin/openssh/` scripts
  if that dir exists (conditions unknown — v8), runs root-side
  `OEMfacstart.sh`, and sets `HI_UI_HOME=/APPS/channelA|channelB` — the UI's
  code lives on our writable `/APPS` too.
- `/proc/uptime` read: 26.3 h — no reboot has occurred during the session, so
  cross-reboot `/APPS` persistence (marker test) is still formally unverified;
  `/APPS` is an e2fsck'd ext4 data partition, so it persists.

### 10.10 Driving the TV remotely; hook armed

- **`launchapp` accepts an arbitrary `http` URL** (`urlType: "1"`): the server's
  new `/api/open?url=…` endpoint loads any page on the TV through the existing
  MQTT session — recon no longer needs the physical remote. The TV browser
  executing attacker/server-chosen URLs is also the silent-load version of the
  Bananamafia install attack: DNS-block the TV from the open web.
- The broker permits **one session per credential set**: a second client dies at
  publish time with the same username/password, whether its client_id matches or
  not. Publish through the running server's connection instead.
- **ICMP echo is disabled by firmware** (`rc.local`: `icmp_echo_ignore_all`) —
  reachability checks must use TCP (36669 MQTT is the reliable probe).
- Root hook status: `/var/local/otaTest.sh` written and readback-verified.
  `/proc/uptime` proved the first "reboot" was a standby cycle — the hook fires
  on the first real power cycle (wall-plug pull or Settings → restart).

### 10.11 Root confirmed: the hook fired, and what it harvested

- After a real power cycle (uptime 250 s), `/var/local/otaTest.sh` executed as
  root at boot. Proof: `/var/local/otaTest.log` exists but is root-owned
  (EACCES for uid 314 — v1 forgot to chmod its own log), and the hook's
  `chmod 644`-ed dumps under `/var/local/rootdumps/` are bridge-readable.
- **`/etc/shadow` harvested**: `root:$6$<redacted>$…`; `television` and
  `cli` share one hash (`$6$<redacted>$…`).
- **`rootlogin.sh` is a two-liner**: `source /usr/local/scripts/key_check.sh; main`
  — the UART root shell is exactly the USB-key gate; there is no separate root
  password prompt (the shadow hash exists for login(1) paths).
- **`cli_login.sh`** (the serial debug CLI, 2024-dated, by Hisense): loads an
  encrypted + RSA-signed `vidaa_commands.bin` package from USB, decrypts with
  `keystore 9602_tv_openssl openssl enc -aes-256-cbc -pass file:/etc/0001-cli-login-aes.pem -pbkdf2 -iter 100000`,
  verifies against `/etc/0002-cli-login-sign-public.pem`. The keystore-wrapped
  AES key and the public key are root-only files — hook v2 copies them into the
  dumps.
- `busybox telnetd` did not produce a listener on 2323 → the applet is most
  likely absent from this build (v2 dumps `busybox --list`, every daemon
  directory, `/proc/net/tcp`, and attempts `telnetd` variants plus
  `busybox nc -l -p 2324 -e /bin/sh`).
- Remote-installed via `hookinstall.html` (auto-writes the hook, backs up the
  previous one to `/var/local/otaTest.v1.bak`) opened through
  `/api/open` — no physical interaction. The Pi journal shows the TV browser
  fetching each page (`GET /hookcheck.html`, `POST /api/recon`).
- The hook's boot-time `wget` phone-home never reached the server: rc.local
  runs before the network stack is fully up. Boot-time reporting needs a sleep
  or retry in the hook.

### 10.12 v2 harvest: the toolbox, and the root-shell plan

- **Busybox applet inventory**: full toolset (dd, tar, gzip, nslookup, ping, ip,
  netstat, ps, mount, chroot, nanddump, **reboot**, poweroff, vi, awk, jq …) —
  but **no `nc`, `telnetd`, `wget`, `httpd`, `ftpget`** (errors captured verbatim:
  `telnetd: applet not found`, `nc: applet not found`).
- `/bin/sh` → `/openbox/bin/bash` — real bash, so **`/dev/tcp/host/port` works as
  a raw TCP client with zero binaries**. That is the network primitive.
- `/usr/local/bin` (ro) holds the crown jewels: **`iptables`** (full netfilter
  control — ad/telemetry blocking lives here), **`opkg` + `ipk-decrypt` +
  `ipk-update` + `app_upgrade`** (the IPK package channel),
  **`openssl`**, `7za`, `unzip`, `jq`, **`screenshot`**, `keystore`, `envAccess`/
  `envClient` (uboot env), `secure_exec`, `masman`, `superwatch(_server)`,
  `deploy`, `factory_lite`, `streamingdaemon`, `r2tcpserver`, and the
  telemetry stack: **`hi_logreport_service`, `mdharvester`, `write_stat`,
  `bizm`, `syslogviewer`**. Kilby (JS-service framework) lives at
  `/usr/local/kilby` and `/usr/local/varlocal/kilby`.
- Boot-time listeners: only loopback — `127.0.0.1:12321` (masman), `127.0.0.1:2121`
  (uid 337). MQTT 36669 comes up later.
- **Root-shell plan (v3, installed)**: static musl `busybox-armv7l` 1.31 (has
  `telnetd`) staged on the Pi behind a raw TCP file server on :4444; the hook
  waits for the network, fetches it over bash `/dev/tcp`, chmods it, starts
  `telnetd -p 2323 -l /bin/sh`. From then on reboots are remote (`reboot`
  binary) — no more plug pulls. Hook v1/v2 preserved in
  `/var/local/otaTest.v1.bak` on the TV.
