# Firmware notes — what's in the images worth knowing (Oct 30)

> Working notes from the 12-partition dump (all paths under
> `pi:~/firmware/extract/` unless noted). Companion to the endpoint map
> (09-endpoints.md) — this file is the "what else is in there" tour.

## 1. The dynamic domain map — the TV publishes its own endpoint list

`/APPS/domain/domain_list.json` (written at runtime by
`jhkservice/dynamicDomain.js`, fetched from `domain.vidaahub.com` with a
cloud token; `ReleaseDate: 2026-07-06`, per-area variants — ours is
`DomainArea: "na"`). Complete map extracted from the p41 image:

- **events/telemetry**: `evt-na.vidaahub.com` (the event sink),
  `ter/exc/policy-jrnl-na.vidaahub.com` (journals: terminal/exception/
  policy), `dvcstatus-dataretriv.vidaahub.com` (device status),
  `file-ul.vidaahub.com` (uploads)
- **ads**: `rsc-ads.vidaahub.com` — named `ads` in the config
- **voice** (7): voice/amazon-voice/vidaa-voice-na/tts/partners/google/
  iot-voice-na
- **msg** (3): hub-msg, prmandroid-msg-na, params-msg-na
- **store/pay**: appstore-vidaa, odinstore-vidaa, pay-vidaa, sport-vidaa,
  tvmodules-vidaa, app-tv, abtest-tv
- **base**: geo-bas-na, bas-na, time-bas-na; **ai**: base-ai;
  **domain**: domain.vidaahub.com (the updater of this very file)

**Two critical properties:**

1. **DoH evasion is explicit**: `dohServers: ["dns.google/dns-query"]` with
   `dohDomains: ["vidaahub.com"]` — vidaahub lookups bypass the LAN
   resolver (AdGuard) via DNS-over-HTTPS *by design*. DNS-layer blocking
   of vidaahub domains requires blocking `dns.google` bootstrap + DoH
   itself, or router-level IP blocks.
2. **The map is a writable file**: `/APPS/domain/domain_list.json` is
   written by phoenix (uid 314) via the bridge's mode-6 base — poisonable
   from a page with no traversal (redirect any vidaahub service to an
   arbitrary host, or point the telemetry sinks at a black hole). The file
   is md5-stamped (`"md5": "032da1b9…"`) — the consumer may verify.

## 2. On-box tooling worth knowing (`/usr/local/bin`)

`iptables` (full netfilter), `opkg` + `ipk-decrypt` + `app_upgrade`,
`openssl`, `7za`, `unzip`, `jq`, **`screenshot`** (framebuffer capture),
`iperf`, `wpa_cli`, `keystore`, `envAccess`/`envClient` (uboot env),
`secure_exec` (signature-gated exec wrapper), `superwatch(_server)`
(process supervisor — resurrects phoenix), `r2tcpserver`, `dectool`
(OEM archive crypto), `mdharvester`, `hi_logreport_service`,
`write_stat`, `bizm`. Busybox applets are NOT symlinked system-wide —
use `/usr/local/bin/busybox <applet>`; `tail`/`pgrep`/`nohup`/`scp`/
`timeout` do not exist as commands.

## 3. JS service packages (the phoenix API surface)

- `tv.vidaa.jsservice.basic/CHA/services/`: **hiutils** (file bridge,
  devtools switch, security codes — see 03), **tvinfo** (~150 params,
  ungated writes), **fetcher**, **ipchandler**
- `tv.vidaa.jsservice.system/CHA/services/`: **jhkservice** (token.js,
  **dynamicDomain.js** — the domain-map updater, appConfigs, appSwitch,
  eposUpgrade, channelList, notification, refreshSysTime), **pkgmgr**
  (IPK install machinery), **pkghosting**, **tilesService**
- `tv.vidaa.jsservice.modules` — exists on /opt, not /APPS (generation
  difference; EU_A 09.60 reportedly lacks it)

## 4. Package-manager metadata on /APPS/pkgs (and /opt/pkgs)

`appinfo.json`, `serviceinfo.json`, `pkgAppInfo.json`, `opkgmeta(+_oad.bk,
_apps.bk)`, `opkg.conf`, and **`rsa_public_2048.key` / `rsa_public_4096.key`**
— the package-signature public keys, world-readable on the rw partition.
IPK forging still requires the private/keystore-wrapped side (`ipk-decrypt`,
`keystore 9602_tv_openssl …`), which is root-only on a stock box.

## 5. euladpp — the consent/telemetry control plane

`/APPS/euladpp/` (rw): `eulaDpp.tar.gz` + `current/` with
`eula_dpp_status.ini` and seven consent sections (`pn1_hbbtv` …
`pn7_registration` — hbbtv, account, voice, enhance, improvement,
management, registration). Root-run boot scripts repair/upgrade it from
the tarball (see 04). This is the settings-layer telemetry switch the
wiretap baseline measures against.

## 6. Loose ends worth a look

- `/usr/local/configuration/options/dclkeys.cfg` — Loewe DCL chassis
  config (HL1); hotel-mode, EPG, quick-start intervals are keys here.
- `/usr/local/kilby/` — per-brand channel service lists + `huangdao.db`
  (SQLite) — channel-list algorithm inputs.
- `mosquitto` broker: runs as its own user with listeners on 1883 (plain,
  0.0.0.0), 36669 (TLS), 11600/11601/16668/16669/10001/11679 — config not
  in the rootfs `/etc`; the 1883 listener is firewalled at the kernel
  layer only.
- `/usr/local/bin/screenshot` — root framebuffer capture.
- `/usr/local/etc/apm/` — app-memory-config, app_key_map (the app
  manager's per-app budget/keys).
- `process.env.json` (hisenseUI): `REPORT: false` in the build snapshot.

## 7. Audio: the ALSA capture lane is dead on this model (2026-11-06)

The userspace-visible ALSA stack looks usable — card 0 `MStar-MAD`, five
`mad_pcm` devices each `playback 1 : capture 1`, `/dev/snd/pcmC0D0{c,p}`
present (`root:mi 660`) — but it carries no audio. The capture probe
([tools/audio/](../../../../../tools/audio/README.md) — links against the
TV's own `/vendor/lib/libasound.so.2`; full method and evidence there)
measured: `hw:0,0` opens, `set_params` and `snd_pcm_start` succeed, then
**every `snd_pcm_readi` returns EIO** (`snd_pcm_recover` −5, `frames=0`).
The EIO is the correct answer, not a failure: during playback **all ten
PCMs report `closed`** in `/proc/asound/card0/pcm*/sub0/status` — tested
with audio going to an optical (S-PDIF) speaker **and** to the internal
speakers, same result both ways, which rules out "tested the wrong
output". Conclusion: the TV's audio never enters a userspace ALSA stream;
the `mad_pcm` nodes are the MStar decoder's internal interface, not the
output mix. Consequence: **snapcast and librespot are not viable through
ALSA on this model** (issue #19) — an architecture answer, not a build
one. One path stays untested and is labelled as such: the TV browser
(`odin`) declares `--alsa-output-device=default;hw:0,0;…`, so audio
played *in a web page* might open a PCM a native app does not.
